"""On-disk session library under ``.apeSketch/sessions/``.

A "recorded" session is a saved Document (``.apesketch.json``) plus metadata,
not a WebM download. Assets stay in the shared AssetStore.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apeSketch.document import Document
from apeSketch.errors import DocumentError

DEFAULT_SESSIONS_DIR = Path(".apeSketch") / "sessions"
_DOC_NAME = "document.apesketch.json"
_META_NAME = "meta.json"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return f"s{secrets.token_hex(4)}"


@dataclass(frozen=True)
class SessionMeta:
    id: str
    title: str
    created_at: str
    updated_at: str
    revision: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMeta:
        sid = data.get("id")
        title = data.get("title", "Untitled")
        created = data.get("created_at")
        updated = data.get("updated_at")
        revision = data.get("revision", 0)
        if not isinstance(sid, str) or not sid:
            raise DocumentError("session meta id required")
        if not isinstance(title, str):
            raise DocumentError("session meta title must be a string")
        if not isinstance(created, str) or not isinstance(updated, str):
            raise DocumentError("session meta timestamps required")
        if not isinstance(revision, int) or revision < 0:
            raise DocumentError("session meta revision must be a non-negative int")
        return cls(
            id=sid,
            title=title.strip() or "Untitled",
            created_at=created,
            updated_at=updated,
            revision=revision,
        )


class SessionStore:
    """CRUD for named board sessions on disk."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, session_id: str) -> Path:
        if not _ID_RE.match(session_id):
            raise DocumentError("invalid session id")
        return self.root / session_id

    def _meta_path(self, session_id: str) -> Path:
        return self._dir(session_id) / _META_NAME

    def _doc_path(self, session_id: str) -> Path:
        return self._dir(session_id) / _DOC_NAME

    def _read_meta(self, session_id: str) -> SessionMeta:
        path = self._meta_path(session_id)
        if not path.is_file():
            raise DocumentError(f"unknown session {session_id!r}")
        try:
            parsed: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DocumentError(f"corrupt session meta {session_id!r}") from exc
        if not isinstance(parsed, dict):
            raise DocumentError(f"corrupt session meta {session_id!r}")
        data = {str(k): v for k, v in parsed.items()}
        data.setdefault("id", session_id)
        return SessionMeta.from_dict(data)

    def _write_meta(self, meta: SessionMeta) -> None:
        path = self._meta_path(meta.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta.to_dict(), indent=2) + "\n", encoding="utf-8")

    def list(self) -> list[SessionMeta]:
        items: list[SessionMeta] = []
        if not self.root.is_dir():
            return items
        for child in self.root.iterdir():
            if not child.is_dir():
                continue
            if not (child / _META_NAME).is_file() or not (child / _DOC_NAME).is_file():
                continue
            try:
                items.append(self._read_meta(child.name))
            except DocumentError:
                continue
        items.sort(key=lambda m: m.updated_at, reverse=True)
        return items

    def create(
        self,
        document: Document,
        *,
        title: str | None = None,
        session_id: str | None = None,
    ) -> SessionMeta:
        sid = session_id or _new_id()
        if session_id is not None and not _ID_RE.match(sid):
            raise DocumentError("invalid session id")
        while self._dir(sid).exists():
            sid = _new_id()
        now = _utc_now()
        meta = SessionMeta(
            id=sid,
            title=(title or "").strip() or "Untitled",
            created_at=now,
            updated_at=now,
            revision=document.revision,
        )
        folder = self._dir(sid)
        folder.mkdir(parents=True, exist_ok=False)
        document.save(self._doc_path(sid))
        self._write_meta(meta)
        return meta

    def save(
        self,
        session_id: str,
        document: Document,
        *,
        title: str | None = None,
    ) -> SessionMeta:
        folder = self._dir(session_id)
        if not folder.is_dir():
            raise DocumentError(f"unknown session {session_id!r}")
        try:
            prev = self._read_meta(session_id)
            created = prev.created_at
            next_title = prev.title
        except DocumentError:
            created = _utc_now()
            next_title = "Untitled"
        if title is not None:
            next_title = title.strip() or "Untitled"
        meta = SessionMeta(
            id=session_id,
            title=next_title,
            created_at=created,
            updated_at=_utc_now(),
            revision=document.revision,
        )
        document.save(self._doc_path(session_id))
        self._write_meta(meta)
        return meta

    def load(self, session_id: str) -> tuple[SessionMeta, Document]:
        meta = self._read_meta(session_id)
        path = self._doc_path(session_id)
        if not path.is_file():
            raise DocumentError(f"missing document for session {session_id!r}")
        return meta, Document.load(path)

    def rename(self, session_id: str, title: str) -> SessionMeta:
        meta = self._read_meta(session_id)
        updated = SessionMeta(
            id=meta.id,
            title=title.strip() or "Untitled",
            created_at=meta.created_at,
            updated_at=_utc_now(),
            revision=meta.revision,
        )
        self._write_meta(updated)
        return updated

    def delete(self, session_id: str) -> None:
        folder = self._dir(session_id)
        if not folder.is_dir():
            raise DocumentError(f"unknown session {session_id!r}")
        for name in (_DOC_NAME, _META_NAME):
            path = folder / name
            if path.is_file():
                path.unlink()
        try:
            folder.rmdir()
        except OSError as exc:
            raise DocumentError(f"could not delete session {session_id!r}") from exc

    def latest(self) -> SessionMeta | None:
        items = self.list()
        return items[0] if items else None
