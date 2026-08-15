"""Live Session: Document authority for LAN clients (ADR 0003, 0004)."""

from __future__ import annotations

import secrets
import string
from typing import Any, Callable

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

    def __init__(self, document: Document | None = None) -> None:
        self.document = document if document is not None else Document()
        self.room_code = _room_code()
        self.token = secrets.token_urlsafe(16)
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Listener) -> None:
        self._listeners = [item for item in self._listeners if item is not listener]

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
        return message

    def apply_dict(
        self, data: dict[str, Any], *, exclude: Listener | None = None
    ) -> dict[str, Any]:
        return self.apply(op_from_dict(data), exclude=exclude)

    def snapshot_message(self) -> dict[str, Any]:
        return {
            "type": "snapshot",
            "rev": self.document.revision,
            "document": self.document.to_dict(),
        }

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
