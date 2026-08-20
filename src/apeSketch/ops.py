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


@dataclass(frozen=True, slots=True)
class AddText:
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
        object.__setattr__(self, "text_id", _require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
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
        if self.blocks is not None:
            # Validate via types.parse_blocks
            from apeSketch.types import parse_blocks

            try:
                parse_blocks(list(self.blocks), content=self.content)
            except ValueError as exc:
                raise DocumentError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class SetTextContent:
    text_id: str
    content: str
    page_id: str = "p0"
    blocks: tuple[dict[str, Any], ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", _require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
        if not isinstance(self.content, str):
            raise DocumentError("content must be a string")
        if self.blocks is not None:
            from apeSketch.types import parse_blocks

            try:
                parse_blocks(list(self.blocks), content=self.content)
            except ValueError as exc:
                raise DocumentError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class SetTextStyle:
    text_id: str
    font_size: float | None = None
    color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", _require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
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


@dataclass(frozen=True, slots=True)
class TransformText:
    text_id: str
    x: float
    y: float
    width: float
    height: float
    font_size: float | None = None
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", _require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
        if self.width <= 0 or self.height <= 0:
            raise DocumentError("text width/height must be positive")
        if self.font_size is not None and self.font_size <= 0:
            raise DocumentError("font_size must be positive")


@dataclass(frozen=True, slots=True)
class EraseText:
    text_id: str
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", _require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))


@dataclass(frozen=True, slots=True)
class SetTextLock:
    text_id: str
    locked: bool
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "text_id", _require_id("text_id", self.text_id))
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))


@dataclass(frozen=True, slots=True)
class MoveStrokes:
    stroke_ids: tuple[str, ...]
    dx: float
    dy: float
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
        if len(self.stroke_ids) == 0:
            raise DocumentError("move_strokes needs at least one stroke_id")
        ids = tuple(_require_id("stroke_id", sid) for sid in self.stroke_ids)
        object.__setattr__(self, "stroke_ids", ids)


@dataclass(frozen=True, slots=True)
class SetStrokeStyle:
    stroke_ids: tuple[str, ...]
    color: str | None = None
    width: float | None = None
    page_id: str = "p0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "page_id", _require_id("page_id", self.page_id))
        if len(self.stroke_ids) == 0:
            raise DocumentError("set_stroke_style needs at least one stroke_id")
        if self.color is None and self.width is None:
            raise DocumentError("set_stroke_style needs at least one style field")
        ids = tuple(_require_id("stroke_id", sid) for sid in self.stroke_ids)
        object.__setattr__(self, "stroke_ids", ids)
        if self.color is not None:
            color = self.color.strip()
            if color == "":
                raise DocumentError("color must be non-empty")
            object.__setattr__(self, "color", color)
        if self.width is not None and self.width <= 0:
            raise DocumentError("width must be positive")


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
    | AddText
    | SetTextContent
    | SetTextStyle
    | TransformText
    | EraseText
    | SetTextLock
    | MoveStrokes
    | SetStrokeStyle
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
    if isinstance(op, AddText):
        payload = {
            "op": "add_text",
            "text_id": op.text_id,
            "content": op.content,
            "x": op.x,
            "y": op.y,
            "width": op.width,
            "height": op.height,
            "font_size": op.font_size,
            "color": op.color,
            "bold": op.bold,
            "italic": op.italic,
            "author": op.author,
            "layer": op.layer,
            "page_id": op.page_id,
        }
        if op.blocks is not None:
            payload["blocks"] = list(op.blocks)
        return payload
    if isinstance(op, SetTextContent):
        payload = {
            "op": "set_text_content",
            "text_id": op.text_id,
            "content": op.content,
            "page_id": op.page_id,
        }
        if op.blocks is not None:
            payload["blocks"] = list(op.blocks)
        return payload
    if isinstance(op, SetTextStyle):
        payload = {
            "op": "set_text_style",
            "text_id": op.text_id,
            "page_id": op.page_id,
        }
        if op.font_size is not None:
            payload["font_size"] = op.font_size
        if op.color is not None:
            payload["color"] = op.color
        if op.bold is not None:
            payload["bold"] = op.bold
        if op.italic is not None:
            payload["italic"] = op.italic
        return payload
    if isinstance(op, TransformText):
        payload = {
            "op": "transform_text",
            "text_id": op.text_id,
            "x": op.x,
            "y": op.y,
            "width": op.width,
            "height": op.height,
            "page_id": op.page_id,
        }
        if op.font_size is not None:
            payload["font_size"] = op.font_size
        return payload
    if isinstance(op, EraseText):
        return {"op": "erase_text", "text_id": op.text_id, "page_id": op.page_id}
    if isinstance(op, SetTextLock):
        return {
            "op": "set_text_lock",
            "text_id": op.text_id,
            "locked": op.locked,
            "page_id": op.page_id,
        }
    if isinstance(op, MoveStrokes):
        return {
            "op": "move_strokes",
            "stroke_ids": list(op.stroke_ids),
            "dx": op.dx,
            "dy": op.dy,
            "page_id": op.page_id,
        }
    if isinstance(op, SetStrokeStyle):
        payload = {
            "op": "set_stroke_style",
            "stroke_ids": list(op.stroke_ids),
            "page_id": op.page_id,
        }
        if op.color is not None:
            payload["color"] = op.color
        if op.width is not None:
            payload["width"] = op.width
        return payload
    raise DocumentError(f"unknown op type {type(op)!r}")


def _blocks_tuple(data: dict[str, Any]) -> tuple[dict[str, Any], ...] | None:
    raw = data.get("blocks")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise DocumentError("blocks must be a list")
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise DocumentError("each block must be an object")
        out.append({str(k): v for k, v in item.items()})
    return tuple(out)


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

    if kind == "add_text":
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
        if not all(isinstance(v, (int, float)) for v in (x, y, width, height, font_size)):
            raise DocumentError("text geometry must be numbers")
        if not isinstance(color, str) or not isinstance(author, str) or not isinstance(layer, str):
            raise DocumentError("color/author/layer must be strings")
        if not isinstance(bold, bool) or not isinstance(italic, bool):
            raise DocumentError("bold/italic must be bools")
        return AddText(
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
            blocks=_blocks_tuple(data),
        )

    if kind == "set_text_content":
        text_id = data.get("text_id")
        content = data.get("content")
        if not isinstance(text_id, str) or not isinstance(content, str):
            raise DocumentError("text_id/content must be strings")
        return SetTextContent(
            text_id=text_id,
            content=content,
            page_id=page_id,
            blocks=_blocks_tuple(data),
        )

    if kind == "set_text_style":
        text_id = data.get("text_id")
        if not isinstance(text_id, str):
            raise DocumentError("text_id must be a string")
        font_size = data.get("font_size")
        color = data.get("color")
        bold = data.get("bold")
        italic = data.get("italic")
        fs: float | None
        if font_size is None:
            fs = None
        elif isinstance(font_size, (int, float)):
            fs = float(font_size)
        else:
            raise DocumentError("font_size must be a number")
        if color is not None and not isinstance(color, str):
            raise DocumentError("color must be a string")
        if bold is not None and not isinstance(bold, bool):
            raise DocumentError("bold must be a bool")
        if italic is not None and not isinstance(italic, bool):
            raise DocumentError("italic must be a bool")
        return SetTextStyle(
            text_id=text_id,
            font_size=fs,
            color=color,
            bold=bold,
            italic=italic,
            page_id=page_id,
        )

    if kind == "transform_text":
        text_id = data.get("text_id")
        if not isinstance(text_id, str):
            raise DocumentError("text_id must be a string")
        x = data.get("x")
        y = data.get("y")
        width = data.get("width")
        height = data.get("height")
        font_size = data.get("font_size")
        if not all(isinstance(v, (int, float)) for v in (x, y, width, height)):
            raise DocumentError("transform_text needs numeric x/y/width/height")
        fs: float | None
        if font_size is None:
            fs = None
        elif isinstance(font_size, (int, float)):
            fs = float(font_size)
        else:
            raise DocumentError("font_size must be a number")
        return TransformText(
            text_id=text_id,
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
            font_size=fs,
            page_id=page_id,
        )

    if kind == "erase_text":
        text_id = data.get("text_id")
        if not isinstance(text_id, str):
            raise DocumentError("text_id must be a string")
        return EraseText(text_id=text_id, page_id=page_id)

    if kind == "set_text_lock":
        text_id = data.get("text_id")
        locked = data.get("locked")
        if not isinstance(text_id, str):
            raise DocumentError("text_id must be a string")
        if not isinstance(locked, bool):
            raise DocumentError("locked must be a bool")
        return SetTextLock(text_id=text_id, locked=locked, page_id=page_id)

    if kind == "move_strokes":
        stroke_ids_raw = data.get("stroke_ids")
        if not isinstance(stroke_ids_raw, list) or not stroke_ids_raw:
            raise DocumentError("stroke_ids must be a non-empty list")
        stroke_ids: list[str] = []
        for item in stroke_ids_raw:
            if not isinstance(item, str):
                raise DocumentError("each stroke_id must be a string")
            stroke_ids.append(item)
        dx = data.get("dx")
        dy = data.get("dy")
        if not isinstance(dx, (int, float)) or not isinstance(dy, (int, float)):
            raise DocumentError("dx/dy must be numbers")
        return MoveStrokes(
            stroke_ids=tuple(stroke_ids),
            dx=float(dx),
            dy=float(dy),
            page_id=page_id,
        )

    if kind == "set_stroke_style":
        stroke_ids_raw = data.get("stroke_ids")
        if not isinstance(stroke_ids_raw, list) or not stroke_ids_raw:
            raise DocumentError("stroke_ids must be a non-empty list")
        stroke_ids = []
        for item in stroke_ids_raw:
            if not isinstance(item, str):
                raise DocumentError("each stroke_id must be a string")
            stroke_ids.append(item)
        color = data.get("color")
        width = data.get("width")
        if color is not None and not isinstance(color, str):
            raise DocumentError("color must be a string")
        if width is not None and not isinstance(width, (int, float)):
            raise DocumentError("width must be a number")
        return SetStrokeStyle(
            stroke_ids=tuple(stroke_ids),
            color=color,
            width=float(width) if width is not None else None,
            page_id=page_id,
        )

    raise DocumentError(f"unknown op {kind!r}")
