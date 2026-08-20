"""Stroke ops: capture, edit, and selection-level stroke changes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from apeSketch.errors import DocumentError
from apeSketch.ops._base import points_from_raw, register, require_id, require_str
from apeSketch.types import InkPoint, StrokeStyle


def _style_from_payload(data: dict[str, Any]) -> StrokeStyle | None:
    style_raw = data.get("style")
    if style_raw is None:
        return None
    if not isinstance(style_raw, dict):
        raise DocumentError("style must be an object")
    return StrokeStyle.from_dict({str(k): v for k, v in style_raw.items()})


def _author_layer(data: dict[str, Any], default_layer: str) -> tuple[str, str]:
    author = data.get("author", "")
    layer = data.get("layer", default_layer)
    if not isinstance(author, str) or not isinstance(layer, str):
        raise DocumentError("author/layer must be strings")
    return author, layer


@register
@dataclass(frozen=True, slots=True)
class BeginStroke:
    kind: ClassVar[str] = "begin_stroke"

    stroke_id: str
    author: str = ""
    layer: str = "default"
    style: StrokeStyle | None = None
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        object.__setattr__(self, "layer", self.layer.strip() or "default")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "op": self.kind,
            "stroke_id": self.stroke_id,
            "author": self.author,
            "layer": self.layer,
            "page_id": self.page_id,
        }
        if self.style is not None:
            payload["style"] = self.style.to_dict()
        return payload

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> BeginStroke:
        author, layer = _author_layer(data, "default")
        return cls(
            stroke_id=require_str(data, "stroke_id"),
            author=author,
            layer=layer,
            style=_style_from_payload(data),
            page_id=page_id,
        )


@register
@dataclass(frozen=True, slots=True)
class AppendPoints:
    kind: ClassVar[str] = "append_points"

    stroke_id: str
    points: tuple[InkPoint, ...]
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        if len(self.points) == 0:
            raise DocumentError("append_points needs at least one point")

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.kind,
            "stroke_id": self.stroke_id,
            "page_id": self.page_id,
            "points": [p.to_list() for p in self.points],
        }

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> AppendPoints:
        return cls(
            stroke_id=require_str(data, "stroke_id"),
            points=points_from_raw(data.get("points")),
            page_id=page_id,
        )


@register
@dataclass(frozen=True, slots=True)
class EndStroke:
    kind: ClassVar[str] = "end_stroke"

    stroke_id: str
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))

    def to_dict(self) -> dict[str, Any]:
        return {"op": self.kind, "stroke_id": self.stroke_id, "page_id": self.page_id}

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> EndStroke:
        return cls(stroke_id=require_str(data, "stroke_id"), page_id=page_id)


@register
@dataclass(frozen=True, slots=True)
class EraseStroke:
    kind: ClassVar[str] = "erase_stroke"

    stroke_id: str
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))

    def to_dict(self) -> dict[str, Any]:
        return {"op": self.kind, "stroke_id": self.stroke_id, "page_id": self.page_id}

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> EraseStroke:
        return cls(stroke_id=require_str(data, "stroke_id"), page_id=page_id)


@register
@dataclass(frozen=True, slots=True)
class AddStroke:
    """Insert a finished stroke in one Op (used when splitting after partial erase)."""

    kind: ClassVar[str] = "add_stroke"

    stroke_id: str
    points: tuple[InkPoint, ...]
    author: str = ""
    layer: str = "default"
    style: StrokeStyle | None = None
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        object.__setattr__(self, "layer", self.layer.strip() or "default")
        if len(self.points) < 1:
            raise DocumentError("add_stroke needs at least one point")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "op": self.kind,
            "stroke_id": self.stroke_id,
            "author": self.author,
            "layer": self.layer,
            "page_id": self.page_id,
            "points": [p.to_list() for p in self.points],
        }
        if self.style is not None:
            payload["style"] = self.style.to_dict()
        return payload

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> AddStroke:
        author, layer = _author_layer(data, "default")
        return cls(
            stroke_id=require_str(data, "stroke_id"),
            points=points_from_raw(data.get("points")),
            author=author,
            layer=layer,
            style=_style_from_payload(data),
            page_id=page_id,
        )


@register
@dataclass(frozen=True, slots=True)
class ReplaceStrokePoints:
    """Replace a stroke's points. Empty points deletes the stroke."""

    kind: ClassVar[str] = "replace_stroke_points"

    stroke_id: str
    points: tuple[InkPoint, ...]
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.kind,
            "stroke_id": self.stroke_id,
            "page_id": self.page_id,
            "points": [p.to_list() for p in self.points],
        }

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> ReplaceStrokePoints:
        raw_points = data.get("points", [])
        if not isinstance(raw_points, list):
            raise DocumentError("points must be a list")
        points: tuple[InkPoint, ...]
        if len(raw_points) == 0:
            points = ()
        else:
            points = points_from_raw(raw_points)
        return cls(stroke_id=require_str(data, "stroke_id"), points=points, page_id=page_id)


def _stroke_ids_from_payload(data: dict[str, Any]) -> tuple[str, ...]:
    stroke_ids_raw = data.get("stroke_ids")
    if not isinstance(stroke_ids_raw, list) or not stroke_ids_raw:
        raise DocumentError("stroke_ids must be a non-empty list")
    stroke_ids: list[str] = []
    for item in stroke_ids_raw:
        if not isinstance(item, str):
            raise DocumentError("each stroke_id must be a string")
        stroke_ids.append(item)
    return tuple(stroke_ids)


@register
@dataclass(frozen=True, slots=True)
class MoveStrokes:
    kind: ClassVar[str] = "move_strokes"

    stroke_ids: tuple[str, ...]
    dx: float
    dy: float
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        if len(self.stroke_ids) == 0:
            raise DocumentError("move_strokes needs at least one stroke_id")
        ids = tuple(require_id("stroke_id", sid) for sid in self.stroke_ids)
        object.__setattr__(self, "stroke_ids", ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.kind,
            "stroke_ids": list(self.stroke_ids),
            "dx": self.dx,
            "dy": self.dy,
            "page_id": self.page_id,
        }

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> MoveStrokes:
        dx = data.get("dx")
        dy = data.get("dy")
        if not isinstance(dx, (int, float)) or not isinstance(dy, (int, float)):
            raise DocumentError("dx/dy must be numbers")
        return cls(
            stroke_ids=_stroke_ids_from_payload(data),
            dx=float(dx),
            dy=float(dy),
            page_id=page_id,
        )


@register
@dataclass(frozen=True, slots=True)
class SetStrokeStyle:
    kind: ClassVar[str] = "set_stroke_style"

    stroke_ids: tuple[str, ...]
    color: str | None = None
    width: float | None = None
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "page_id", require_id("page_id", self.page_id))
        if len(self.stroke_ids) == 0:
            raise DocumentError("set_stroke_style needs at least one stroke_id")
        if self.color is None and self.width is None:
            raise DocumentError("set_stroke_style needs at least one style field")
        ids = tuple(require_id("stroke_id", sid) for sid in self.stroke_ids)
        object.__setattr__(self, "stroke_ids", ids)
        if self.color is not None:
            color = self.color.strip()
            if color == "":
                raise DocumentError("color must be non-empty")
            object.__setattr__(self, "color", color)
        if self.width is not None and self.width <= 0:
            raise DocumentError("width must be positive")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "op": self.kind,
            "stroke_ids": list(self.stroke_ids),
            "page_id": self.page_id,
        }
        if self.color is not None:
            payload["color"] = self.color
        if self.width is not None:
            payload["width"] = self.width
        return payload

    @classmethod
    def from_payload(cls, data: dict[str, Any], page_id: str) -> SetStrokeStyle:
        color = data.get("color")
        width = data.get("width")
        if color is not None and not isinstance(color, str):
            raise DocumentError("color must be a string")
        if width is not None and not isinstance(width, (int, float)):
            raise DocumentError("width must be a number")
        return cls(
            stroke_ids=_stroke_ids_from_payload(data),
            color=color,
            width=float(width) if width is not None else None,
            page_id=page_id,
        )
