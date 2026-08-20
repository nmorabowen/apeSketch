"""Page ops: whole-page state changes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from apeSketch.errors import DocumentError
from apeSketch.ops._base import register, require_id


@register
@dataclass(frozen=True, slots=True)
class ClearPage:
    kind: ClassVar[str] = "clear_page"

    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))

    def to_dict(self) -> dict[str, Any]:
        return {"op": self.kind, "page_id": self.page_id}

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> ClearPage:
        return cls(page_id=page_id)


@register
@dataclass(frozen=True, slots=True)
class SetBackground:
    kind: ClassVar[str] = "set_background"

    color: str
    page_id: str = "p0"

    def __post_init__(self) -> None:
        color = self.color.strip()
        if color == "":
            raise DocumentError("background color must be non-empty")
        object.__setattr__(self, "color", color)
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))

    def to_dict(self) -> dict[str, Any]:
        return {"op": self.kind, "color": self.color, "page_id": self.page_id}

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> SetBackground:
        color = data.get("color")
        if not isinstance(color, str):
            raise DocumentError("color must be a string")
        return cls(color=color, page_id=page_id)
