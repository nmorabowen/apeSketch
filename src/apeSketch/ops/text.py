"""Text ops: rich text objects (content, style, transform, lock)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from apeSketch.errors import DocumentError
from apeSketch.ops._base import blocks_tuple, register, require_id, require_str


def _validate_blocks(blocks: tuple[dict[str, Any], ...] | None, content: str) -> None:
    if blocks is None:
        return
    from apeSketch.types import parse_blocks

    try:
        parse_blocks(list(blocks), content=content)
    except ValueError as exc:
        raise DocumentError(str(exc)) from exc


def _optional_font_size(data: dict[str, Any]) -> float | None:
    font_size = data.get("font_size")
    if font_size is None:
        return None
    if isinstance(font_size, (int, float)):
        return float(font_size)
    raise DocumentError("font_size must be a number")


@register
@dataclass(frozen=True, slots=True)
class AddText:
    kind: ClassVar[str] = "add_text"

    text_id: str
    content: str
    x: float
    y: float
    width: float
    height: float
    font_size: float = 28.0
    color: str = "#111111"
    bold: bool = False
    italic: bool = False
    author: str = ""
    layer: str = "text"
    page_id: str = "p0"
    blocks: tuple[dict[str, Any], ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        object.__setattr__(self, "layer", self.layer.strip() or "text")
        if not isinstance(self.content, str):
            raise DocumentError("content must be a string")
        if self.width <= 0 or self.height <= 0 or self.font_size <= 0:
            raise DocumentError("text width/height/font_size must be positive")
        color = self.color.strip()
        if color == "":
            raise DocumentError("color must be non-empty")
        object.__setattr__(self, "color", color)
        if not isinstance(self.bold, bool) or not isinstance(self.italic, bool):
            raise DocumentError("bold/italic must be bools")
        _validate_blocks(self.blocks, self.content)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "op": self.kind,
            "text_id": self.text_id,
            "content": self.content,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "font_size": self.font_size,
            "color": self.color,
            "bold": self.bold,
            "italic": self.italic,
            "author": self.author,
            "layer": self.layer,
            "page_id": self.page_id,
        }
        if self.blocks is not None:
            payload["blocks"] = list(self.blocks)
        return payload

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> AddText:
        text_id = data.get("text_id")
        content = data.get("content", "")
        if not isinstance(text_id, str) or not isinstance(content, str):
            raise DocumentError("text_id/content must be strings")
        x = data.get("x", 0.0)
        y = data.get("y", 0.0)
        width = data.get("width")
        height = data.get("height")
        font_size = data.get("font_size", 28.0)
        color = data.get("color", "#111111")
        bold = data.get("bold", False)
        italic = data.get("italic", False)
        author = data.get("author", "")
        layer = data.get("layer", "text")
        if (
            not isinstance(x, (int, float))
            or not isinstance(y, (int, float))
            or not isinstance(width, (int, float))
            or not isinstance(height, (int, float))
            or not isinstance(font_size, (int, float))
        ):
            raise DocumentError("text geometry must be numbers")
        if not isinstance(color, str) or not isinstance(author, str) or not isinstance(layer, str):
            raise DocumentError("color/author/layer must be strings")
        if not isinstance(bold, bool) or not isinstance(italic, bool):
            raise DocumentError("bold/italic must be bools")
        return cls(
            text_id=text_id,
            content=content,
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
            font_size=float(font_size),
            color=color,
            bold=bold,
            italic=italic,
            author=author,
            layer=layer,
            page_id=page_id,
            blocks=blocks_tuple(data),
        )


@register
@dataclass(frozen=True, slots=True)
class SetTextContent:
    kind: ClassVar[str] = "set_text_content"

    text_id: str
    content: str
    page_id: str = "p0"
    blocks: tuple[dict[str, Any], ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        if not isinstance(self.content, str):
            raise DocumentError("content must be a string")
        _validate_blocks(self.blocks, self.content)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "op": self.kind,
            "text_id": self.text_id,
            "content": self.content,
            "page_id": self.page_id,
        }
        if self.blocks is not None:
            payload["blocks"] = list(self.blocks)
        return payload

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> SetTextContent:
        text_id = data.get("text_id")
        content = data.get("content")
        if not isinstance(text_id, str) or not isinstance(content, str):
            raise DocumentError("text_id/content must be strings")
        return cls(
            text_id=text_id,
            content=content,
            page_id=page_id,
            blocks=blocks_tuple(data),
        )


@register
@dataclass(frozen=True, slots=True)
class SetTextStyle:
    kind: ClassVar[str] = "set_text_style"

    text_id: str
    font_size: float | None = None
    color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        if (
            self.font_size is None
            and self.color is None
            and self.bold is None
            and self.italic is None
        ):
            raise DocumentError("set_text_style needs at least one style field")
        if self.font_size is not None and self.font_size <= 0:
            raise DocumentError("font_size must be positive")
        if self.color is not None:
            color = self.color.strip()
            if color == "":
                raise DocumentError("color must be non-empty")
            object.__setattr__(self, "color", color)
        if self.bold is not None and not isinstance(self.bold, bool):
            raise DocumentError("bold must be a bool")
        if self.italic is not None and not isinstance(self.italic, bool):
            raise DocumentError("italic must be a bool")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "op": self.kind,
            "text_id": self.text_id,
            "page_id": self.page_id,
        }
        if self.font_size is not None:
            payload["font_size"] = self.font_size
        if self.color is not None:
            payload["color"] = self.color
        if self.bold is not None:
            payload["bold"] = self.bold
        if self.italic is not None:
            payload["italic"] = self.italic
        return payload

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> SetTextStyle:
        text_id = require_str(data, "text_id")
        color = data.get("color")
        bold = data.get("bold")
        italic = data.get("italic")
        if color is not None and not isinstance(color, str):
            raise DocumentError("color must be a string")
        if bold is not None and not isinstance(bold, bool):
            raise DocumentError("bold must be a bool")
        if italic is not None and not isinstance(italic, bool):
            raise DocumentError("italic must be a bool")
        return cls(
            text_id=text_id,
            font_size=_optional_font_size(data),
            color=color,
            bold=bold,
            italic=italic,
            page_id=page_id,
        )


@register
@dataclass(frozen=True, slots=True)
class TransformText:
    kind: ClassVar[str] = "transform_text"

    text_id: str
    x: float
    y: float
    width: float
    height: float
    font_size: float | None = None
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        if self.width <= 0 or self.height <= 0:
            raise DocumentError("text width/height must be positive")
        if self.font_size is not None and self.font_size <= 0:
            raise DocumentError("font_size must be positive")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "op": self.kind,
            "text_id": self.text_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "page_id": self.page_id,
        }
        if self.font_size is not None:
            payload["font_size"] = self.font_size
        return payload

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> TransformText:
        text_id = require_str(data, "text_id")
        x = data.get("x")
        y = data.get("y")
        width = data.get("width")
        height = data.get("height")
        if (
            not isinstance(x, (int, float))
            or not isinstance(y, (int, float))
            or not isinstance(width, (int, float))
            or not isinstance(height, (int, float))
        ):
            raise DocumentError("transform_text needs numeric x/y/width/height")
        return cls(
            text_id=text_id,
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
            font_size=_optional_font_size(data),
            page_id=page_id,
        )


@register
@dataclass(frozen=True, slots=True)
class EraseText:
    kind: ClassVar[str] = "erase_text"

    text_id: str
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))

    def to_dict(self) -> dict[str, Any]:
        return {"op": self.kind, "text_id": self.text_id, "page_id": self.page_id}

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> EraseText:
        return cls(text_id=require_str(data, "text_id"), page_id=page_id)


@register
@dataclass(frozen=True, slots=True)
class SetTextLock:
    kind: ClassVar[str] = "set_text_lock"

    text_id: str
    locked: bool
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.kind,
            "text_id": self.text_id,
            "locked": self.locked,
            "page_id": self.page_id,
        }

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> SetTextLock:
        text_id = require_str(data, "text_id")
        locked = data.get("locked")
        if not isinstance(locked, bool):
            raise DocumentError("locked must be a bool")
        return cls(text_id=text_id, locked=locked, page_id=page_id)
