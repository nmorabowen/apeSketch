"""Typed ink operations. The ops log is the document writer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apeSketch.errors import DocumentError
from apeSketch.types import InkPoint, StrokeStyle

SCHEMA_ID = "apeSketch.document.v0"
UNITS = "css_px"


def _require_id(name: str, value: str) -> str:
    stripped = value.strip()
    if stripped == "":
        raise DocumentError(f"{name} must be a non-empty string")
    return stripped


def _points_from_raw(raw: object) -> tuple[InkPoint, ...]:
    if not isinstance(raw, list):
        raise DocumentError("points must be a list")
    points: list[InkPoint] = []
    for item in raw:
        if not isinstance(item, (list, tuple)):
            raise DocumentError("each point must be a list of numbers")
        try:
            points.append(InkPoint.from_list([float(v) for v in item]))
        except (TypeError, ValueError) as exc:
            raise DocumentError(f"invalid point: {exc}") from exc
    return tuple(points)


@dataclass(frozen=True, slots=True)
class BeginStroke:
    stroke_id: str
    author: str = ""
    layer: str = "default"
    style: StrokeStyle | None = None
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", _require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
        object.__setattr__(self, "layer", self.layer.strip() or "default")


@dataclass(frozen=True, slots=True)
class AppendPoints:
    stroke_id: str
    points: tuple[InkPoint, ...]
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", _require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
        if len(self.points) == 0:
            raise DocumentError("append_points needs at least one point")


@dataclass(frozen=True, slots=True)
class EndStroke:
    stroke_id: str
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", _require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))


@dataclass(frozen=True, slots=True)
class EraseStroke:
    stroke_id: str
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", _require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))


@dataclass(frozen=True, slots=True)
class ClearPage:
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))


@dataclass(frozen=True, slots=True)
class SetBackground:
    color: str
    page_id: str = "p0"

    def __post_init__(self) -> None:
        color = self.color.strip()
        if color == "":
            raise DocumentError("background color must be non-empty")
        object.__setattr__(self, "color", color)
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))


@dataclass(frozen=True, slots=True)
class AddStroke:
    """Insert a finished stroke in one Op (used when splitting after partial erase)."""

    stroke_id: str
    points: tuple[InkPoint, ...]
    author: str = ""
    layer: str = "default"
    style: StrokeStyle | None = None
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", _require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
        object.__setattr__(self, "layer", self.layer.strip() or "default")
        if len(self.points) < 1:
            raise DocumentError("add_stroke needs at least one point")


@dataclass(frozen=True, slots=True)
class ReplaceStrokePoints:
    """Replace a stroke's points. Empty points deletes the stroke."""

    stroke_id: str
    points: tuple[InkPoint, ...]
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke_id", _require_id("stroke_id", self.stroke_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))


@dataclass(frozen=True, slots=True)
class AddImage:
    image_id: str
    asset_id: str
    x: float
    y: float
    width: float
    height: float
    author: str = ""
    layer: str = "images"
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_id", _require_id("image_id", self.image_id))
        object.__setattr__(self, "asset_id", _require_id("asset_id", self.asset_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
        object.__setattr__(self, "layer", self.layer.strip() or "images")
        if self.width <= 0 or self.height <= 0:
            raise DocumentError("image width/height must be positive")


@dataclass(frozen=True, slots=True)
class EraseImage:
    image_id: str
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_id", _require_id("image_id", self.image_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))


@dataclass(frozen=True, slots=True)
class TransformImage:
    image_id: str
    x: float
    y: float
    width: float
    height: float
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_id", _require_id("image_id", self.image_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
        if self.width <= 0 or self.height <= 0:
            raise DocumentError("image width/height must be positive")


@dataclass(frozen=True, slots=True)
class SetImageLock:
    image_id: str
    locked: bool
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "image_id", _require_id("image_id", self.image_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))


Op = (
    BeginStroke
    | AppendPoints
    | EndStroke
    | EraseStroke
    | ClearPage
    | SetBackground
    | AddStroke
    | ReplaceStrokePoints
    | AddImage
    | EraseImage
    | TransformImage
    | SetImageLock
)


def op_to_dict(op: Op) -> dict[str, Any]:
    if isinstance(op, BeginStroke):
        payload: dict[str, Any] = {
            "op": "begin_stroke",
            "stroke_id": op.stroke_id,
            "author": op.author,
            "layer": op.layer,
            "page_id": op.page_id,
        }
        if op.style is not None:
            payload["style"] = op.style.to_dict()
        return payload
    if isinstance(op, AppendPoints):
        return {
            "op": "append_points",
            "stroke_id": op.stroke_id,
            "page_id": op.page_id,
            "points": [p.to_list() for p in op.points],
        }
    if isinstance(op, EndStroke):
        return {"op": "end_stroke", "stroke_id": op.stroke_id, "page_id": op.page_id}
    if isinstance(op, EraseStroke):
        return {"op": "erase_stroke", "stroke_id": op.stroke_id, "page_id": op.page_id}
    if isinstance(op, ClearPage):
        return {"op": "clear_page", "page_id": op.page_id}
    if isinstance(op, SetBackground):
        return {"op": "set_background", "color": op.color, "page_id": op.page_id}
    if isinstance(op, AddStroke):
        payload = {
            "op": "add_stroke",
            "stroke_id": op.stroke_id,
            "author": op.author,
            "layer": op.layer,
            "page_id": op.page_id,
            "points": [p.to_list() for p in op.points],
        }
        if op.style is not None:
            payload["style"] = op.style.to_dict()
        return payload
    if isinstance(op, ReplaceStrokePoints):
        return {
            "op": "replace_stroke_points",
            "stroke_id": op.stroke_id,
            "page_id": op.page_id,
            "points": [p.to_list() for p in op.points],
        }
    if isinstance(op, AddImage):
        return {
            "op": "add_image",
            "image_id": op.image_id,
            "asset_id": op.asset_id,
            "x": op.x,
            "y": op.y,
            "width": op.width,
            "height": op.height,
            "author": op.author,
            "layer": op.layer,
            "page_id": op.page_id,
        }
    if isinstance(op, EraseImage):
        return {"op": "erase_image", "image_id": op.image_id, "page_id": op.page_id}
    if isinstance(op, TransformImage):
        return {
            "op": "transform_image",
            "image_id": op.image_id,
            "x": op.x,
            "y": op.y,
            "width": op.width,
            "height": op.height,
            "page_id": op.page_id,
        }
    if isinstance(op, SetImageLock):
        return {
            "op": "set_image_lock",
            "image_id": op.image_id,
            "locked": op.locked,
            "page_id": op.page_id,
        }
    raise DocumentError(f"unknown op type {type(op)!r}")


def op_from_dict(data: dict[str, Any]) -> Op:
    kind = data.get("op")
    if not isinstance(kind, str):
        raise DocumentError("op field must be a string")
    page_id = data.get("page_id", "p0")
    if not isinstance(page_id, str):
        raise DocumentError("page_id must be a string")

    if kind == "begin_stroke":
        stroke_id = data.get("stroke_id")
        if not isinstance(stroke_id, str):
            raise DocumentError("stroke_id must be a string")
        author = data.get("author", "")
        layer = data.get("layer", "default")
        if not isinstance(author, str) or not isinstance(layer, str):
            raise DocumentError("author/layer must be strings")
        style: StrokeStyle | None = None
        style_raw = data.get("style")
        if style_raw is not None:
            if not isinstance(style_raw, dict):
                raise DocumentError("style must be an object")
            style = StrokeStyle.from_dict({str(k): v for k, v in style_raw.items()})
        return BeginStroke(
            stroke_id=stroke_id,
            author=author,
            layer=layer,
            style=style,
            page_id=page_id,
        )

    if kind == "append_points":
        stroke_id = data.get("stroke_id")
        if not isinstance(stroke_id, str):
            raise DocumentError("stroke_id must be a string")
        return AppendPoints(
            stroke_id=stroke_id,
            points=_points_from_raw(data.get("points")),
            page_id=page_id,
        )

    if kind == "end_stroke":
        stroke_id = data.get("stroke_id")
        if not isinstance(stroke_id, str):
            raise DocumentError("stroke_id must be a string")
        return EndStroke(stroke_id=stroke_id, page_id=page_id)

    if kind == "erase_stroke":
        stroke_id = data.get("stroke_id")
        if not isinstance(stroke_id, str):
            raise DocumentError("stroke_id must be a string")
        return EraseStroke(stroke_id=stroke_id, page_id=page_id)

    if kind == "clear_page":
        return ClearPage(page_id=page_id)

    if kind == "set_background":
        color = data.get("color")
        if not isinstance(color, str):
            raise DocumentError("color must be a string")
        return SetBackground(color=color, page_id=page_id)

    if kind == "add_stroke":
        stroke_id = data.get("stroke_id")
        if not isinstance(stroke_id, str):
            raise DocumentError("stroke_id must be a string")
        author = data.get("author", "")
        layer = data.get("layer", "default")
        if not isinstance(author, str) or not isinstance(layer, str):
            raise DocumentError("author/layer must be strings")
        style = None
        style_raw = data.get("style")
        if style_raw is not None:
            if not isinstance(style_raw, dict):
                raise DocumentError("style must be an object")
            style = StrokeStyle.from_dict({str(k): v for k, v in style_raw.items()})
        return AddStroke(
            stroke_id=stroke_id,
            points=_points_from_raw(data.get("points")),
            author=author,
            layer=layer,
            style=style,
            page_id=page_id,
        )

    if kind == "replace_stroke_points":
        stroke_id = data.get("stroke_id")
        if not isinstance(stroke_id, str):
            raise DocumentError("stroke_id must be a string")
        raw_points = data.get("points", [])
        if not isinstance(raw_points, list):
            raise DocumentError("points must be a list")
        points: tuple[InkPoint, ...]
        if len(raw_points) == 0:
            points = ()
        else:
            points = _points_from_raw(raw_points)
        return ReplaceStrokePoints(stroke_id=stroke_id, points=points, page_id=page_id)

    if kind == "add_image":
        image_id = data.get("image_id")
        asset_id = data.get("asset_id")
        if not isinstance(image_id, str) or not isinstance(asset_id, str):
            raise DocumentError("image_id/asset_id must be strings")
        x = data.get("x", 0.0)
        y = data.get("y", 0.0)
        width = data.get("width")
        height = data.get("height")
        author = data.get("author", "")
        layer = data.get("layer", "images")
        if not all(isinstance(v, (int, float)) for v in (x, y)):
            raise DocumentError("image x/y must be numbers")
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            raise DocumentError("image width/height must be numbers")
        if not isinstance(author, str) or not isinstance(layer, str):
            raise DocumentError("author/layer must be strings")
        return AddImage(
            image_id=image_id,
            asset_id=asset_id,
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
            author=author,
            layer=layer,
            page_id=page_id,
        )

    if kind == "erase_image":
        image_id = data.get("image_id")
        if not isinstance(image_id, str):
            raise DocumentError("image_id must be a string")
        return EraseImage(image_id=image_id, page_id=page_id)

    if kind == "transform_image":
        image_id = data.get("image_id")
        if not isinstance(image_id, str):
            raise DocumentError("image_id must be a string")
        x = data.get("x")
        y = data.get("y")
        width = data.get("width")
        height = data.get("height")
        if not all(isinstance(v, (int, float)) for v in (x, y, width, height)):
            raise DocumentError("transform_image needs numeric x/y/width/height")
        return TransformImage(
            image_id=image_id,
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
            page_id=page_id,
        )

    if kind == "set_image_lock":
        image_id = data.get("image_id")
        locked = data.get("locked")
        if not isinstance(image_id, str):
            raise DocumentError("image_id must be a string")
        if not isinstance(locked, bool):
            raise DocumentError("locked must be a bool")
        return SetImageLock(image_id=image_id, locked=locked, page_id=page_id)

    raise DocumentError(f"unknown op {kind!r}")
