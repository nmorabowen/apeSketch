"""Binary asset store for board images (kept out of the ops log)."""

from __future__ import annotations

import base64
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path

from apeSketch.errors import DocumentError

MAX_ASSET_BYTES = 8 * 1024 * 1024
ALLOWED_MIME = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}


@dataclass(frozen=True, slots=True)
class StoredAsset:
    asset_id: str
    mime: str
    data: bytes


class AssetStore:
    """In-memory asset store with optional disk mirror under ``root``."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root
        self._lock = threading.Lock()
        self._items: dict[str, StoredAsset] = {}
        if self._root is not None:
            self._root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, data: bytes, mime: str) -> StoredAsset:
        mime_norm = _normalize_mime(mime)
        sniffed = _sniff_mime(data)
        if sniffed:
            mime_norm = sniffed
        if mime_norm not in ALLOWED_MIME:
            raise DocumentError(f"unsupported image type {mime!r}")
        if not data:
            raise DocumentError("empty asset")
        if len(data) > MAX_ASSET_BYTES:
            raise DocumentError(f"asset exceeds {MAX_ASSET_BYTES} bytes")
        asset_id = f"a-{secrets.token_urlsafe(10)}"
        item = StoredAsset(asset_id=asset_id, mime=mime_norm, data=data)
        with self._lock:
            self._items[asset_id] = item
            if self._root is not None:
                path = self._root / f"{asset_id}{_ext_for_mime(mime_norm)}"
                path.write_bytes(data)
                meta = self._root / f"{asset_id}.mime"
                meta.write_text(mime_norm, encoding="utf-8")
        return item

    def put_base64(self, data_b64: str, mime: str) -> StoredAsset:
        try:
            raw = base64.b64decode(data_b64, validate=False)
        except Exception as exc:  # noqa: BLE001 — surface as DocumentError
            raise DocumentError("invalid base64 asset data") from exc
        return self.put_bytes(raw, mime)

    def get(self, asset_id: str) -> StoredAsset | None:
        with self._lock:
            item = self._items.get(asset_id)
            if item is not None:
                return item
        if self._root is None:
            return None
        for path in self._root.glob(f"{asset_id}.*"):
            if path.suffix == ".mime":
                continue
            mime_path = self._root / f"{asset_id}.mime"
            mime = (
                mime_path.read_text(encoding="utf-8").strip()
                if mime_path.is_file()
                else _mime_for_ext(path.suffix)
            )
            data = path.read_bytes()
            item = StoredAsset(asset_id=asset_id, mime=_normalize_mime(mime), data=data)
            with self._lock:
                self._items[asset_id] = item
            return item
        return None

    def data_uri(self, asset_id: str) -> str | None:
        item = self.get(asset_id)
        if item is None:
            return None
        encoded = base64.b64encode(item.data).decode("ascii")
        return f"data:{item.mime};base64,{encoded}"


def _normalize_mime(mime: str) -> str:
    value = mime.strip().lower()
    if ";" in value:
        value = value.split(";", 1)[0].strip()
    if value == "image/jpg":
        return "image/jpeg"
    return value


def _sniff_mime(data: bytes) -> str | None:
    if len(data) >= 8 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 3 and data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 6 and data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _ext_for_mime(mime: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime, ".bin")


def _mime_for_ext(ext: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext.lower(), "application/octet-stream")
