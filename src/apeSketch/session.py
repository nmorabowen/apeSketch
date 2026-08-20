"""Live Session: Document authority for LAN clients (ADR 0003, 0004)."""

from __future__ import annotations

import secrets
import string
from collections.abc import Callable
from typing import Any

from apeSketch.assets import AssetStore
from apeSketch.document import Document
from apeSketch.errors import DocumentError
from apeSketch.ops import Op, op_from_dict, op_to_dict

Listener = Callable[[dict[str, Any]], None]


def _room_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    # Avoid ambiguous characters.
    alphabet = alphabet.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


class SketchSession:
    """Owns one Document. Clients submit Ops; listeners get broadcasts."""

    def __init__(
        self,
        document: Document | None = None,
        *,
        assets: AssetStore | None = None,
    ) -> None:
        self.document = document if document is not None else Document()
        self.assets = assets if assets is not None else AssetStore()
        self.room_code = _room_code()
        self.token = secrets.token_urlsafe(16)
        self._listeners: list[Listener] = []
        self._change_listeners: list[Listener] = []
        self.session_id: str | None = None
        self.session_title: str = "Untitled"

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Listener) -> None:
        self._listeners = [item for item in self._listeners if item is not listener]

    def on_change(self, listener: Listener) -> None:
        """Notify after the document mutates (for autosave, etc.)."""
        self._change_listeners.append(listener)

    def _notify_change(self) -> None:
        message = {
            "type": "change",
            "rev": self.document.revision,
            "session_id": self.session_id,
        }
        for listener in list(self._change_listeners):
            listener(message)

    def apply(self, op: Op, *, exclude: Listener | None = None) -> dict[str, Any]:
        self.document.apply(op)
        message = {
            "type": "op",
            "rev": self.document.revision,
            "op": op_to_dict(op),
        }
        for listener in list(self._listeners):
            if exclude is not None and listener is exclude:
                continue
            listener(message)
        self._notify_change()
        return message

    def apply_dict(
        self, data: dict[str, Any], *, exclude: Listener | None = None
    ) -> dict[str, Any]:
        return self.apply(op_from_dict(data), exclude=exclude)

    def apply_many_dicts(
        self, items: list[dict[str, Any]], *, exclude: Listener | None = None
    ) -> dict[str, Any]:
        """Apply several ops.

        Clients may upload a batched ``ops`` message; we still broadcast each
        change as a normal ``op`` so older board.js clients stay in sync.
        """
        if not items:
            return {"type": "ops", "rev": self.document.revision, "ops": []}
        encoded: list[dict[str, Any]] = []
        for data in items:
            op = op_from_dict(data)
            self.document.apply(op)
            payload = op_to_dict(op)
            encoded.append(payload)
            message = {
                "type": "op",
                "rev": self.document.revision,
                "op": payload,
            }
            for listener in list(self._listeners):
                if exclude is not None and listener is exclude:
                    continue
                listener(message)
        self._notify_change()
        return {
            "type": "ops",
            "rev": self.document.revision,
            "ops": encoded,
        }

    def snapshot_message(self) -> dict[str, Any]:
        message: dict[str, Any] = {
            "type": "snapshot",
            "rev": self.document.revision,
            "document": self.document.to_dict(),
        }
        if self.session_id is not None:
            message["session"] = {
                "id": self.session_id,
                "title": self.session_title,
            }
        return message

    def broadcast_snapshot(self) -> dict[str, Any]:
        message = self.snapshot_message()
        for listener in list(self._listeners):
            listener(message)
        return message

    def replace_document(
        self,
        document: Document,
        *,
        session_id: str | None = None,
        session_title: str = "Untitled",
    ) -> dict[str, Any]:
        """Swap the live Document and push a full snapshot to clients."""
        self.document = document
        self.session_id = session_id
        self.session_title = session_title.strip() or "Untitled"
        return self.broadcast_snapshot()

    def bind_session(self, session_id: str | None, title: str = "Untitled") -> None:
        self.session_id = session_id
        self.session_title = title.strip() or "Untitled"

    def pair_info(self, *, host: str, port: int, scheme: str = "ws") -> dict[str, Any]:
        ws_url = f"{scheme}://{host}:{port}/ws?room={self.room_code}&token={self.token}"
        return {
            "room": self.room_code,
            "token": self.token,
            "ws": ws_url,
            "board": f"http://{host}:{port}/",
            "pair": f"http://{host}:{port}/pair",
        }

    def authorize(self, room: str, token: str) -> None:
        if room != self.room_code or token != self.token:
            raise DocumentError("invalid room or token")
