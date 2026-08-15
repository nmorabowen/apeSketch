"""Ink geometry types for the Document."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class InkPoint:
    """One sample in page space (prototype units: CSS pixels, top-left origin)."""

    x: float
    y: float
    t: float
    pressure: float = 0.5

    def to_list(self) -> list[float]:
        return [self.x, self.y, self.t, self.pressure]

    @classmethod
    def from_list(cls, values: list[float] | tuple[float, ...]) -> InkPoint:
        if len(values) < 3:
            raise ValueError("point needs at least x, y, t")
        pressure = float(values[3]) if len(values) > 3 else 0.5
        return cls(x=float(values[0]), y=float(values[1]), t=float(values[2]), pressure=pressure)


@dataclass(frozen=True, slots=True)
class StrokeStyle:
    color: str = "#111111"
    width: float = 2.0
    kind: str = "pen"  # pen | fountain | chalk
    tip: str = "round"  # round | square | chisel

    def to_dict(self) -> dict[str, object]:
        return {
            "color": self.color,
            "width": self.width,
            "kind": self.kind,
            "tip": self.tip,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> StrokeStyle:
        color = data.get("color", "#111111")
        width = data.get("width", 2.0)
        kind = data.get("kind", "pen")
        tip = data.get("tip", "round")
        if not isinstance(color, str):
            raise ValueError("style.color must be a string")
        if not isinstance(width, (int, float)):
            raise ValueError("style.width must be a number")
        if not isinstance(kind, str) or kind not in {"pen", "fountain", "chalk"}:
            raise ValueError("style.kind must be pen, fountain, or chalk")
        if not isinstance(tip, str) or tip not in {"round", "square", "chisel"}:
            raise ValueError("style.tip must be round, square, or chisel")
        return cls(color=color, width=float(width), kind=kind, tip=tip)


@dataclass(slots=True)
class Stroke:
    stroke_id: str
    points: list[InkPoint] = field(default_factory=list)
    style: StrokeStyle = field(default_factory=StrokeStyle)
    layer: str = "default"
    author: str = ""
    open: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "stroke_id": self.stroke_id,
            "points": [p.to_list() for p in self.points],
            "style": self.style.to_dict(),
            "layer": self.layer,
            "author": self.author,
            "open": self.open,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Stroke:
        stroke_id = data.get("stroke_id")
        if not isinstance(stroke_id, str) or stroke_id == "":
            raise ValueError("stroke_id must be a non-empty string")
        raw_points = data.get("points", [])
        if not isinstance(raw_points, list):
            raise ValueError("points must be a list")
        points: list[InkPoint] = []
        for item in raw_points:
            if not isinstance(item, (list, tuple)):
                raise ValueError("each point must be a list")
            points.append(InkPoint.from_list([float(v) for v in item]))
        style_raw = data.get("style", {})
        if style_raw is None:
            style_raw = {}
        if not isinstance(style_raw, dict):
            raise ValueError("style must be an object")
        style = StrokeStyle.from_dict({str(k): v for k, v in style_raw.items()})
        layer = data.get("layer", "default")
        author = data.get("author", "")
        open_flag = data.get("open", False)
        if not isinstance(layer, str):
            raise ValueError("layer must be a string")
        if not isinstance(author, str):
            raise ValueError("author must be a string")
        if not isinstance(open_flag, bool):
            raise ValueError("open must be a bool")
        return cls(
            stroke_id=stroke_id,
            points=points,
            style=style,
            layer=layer,
            author=author,
            open=open_flag,
        )


@dataclass(slots=True)
class ImageObject:
    """Raster placed on the page (bytes live in AssetStore via asset_id)."""

    image_id: str
    asset_id: str
    x: float
    y: float
    width: float
    height: float
    author: str = ""
    layer: str = "images"
    locked: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "image_id": self.image_id,
            "asset_id": self.asset_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "author": self.author,
            "layer": self.layer,
            "locked": self.locked,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ImageObject:
        image_id = data.get("image_id")
        asset_id = data.get("asset_id")
        if not isinstance(image_id, str) or image_id == "":
            raise ValueError("image_id must be a non-empty string")
        if not isinstance(asset_id, str) or asset_id == "":
            raise ValueError("asset_id must be a non-empty string")
        x = data.get("x", 0.0)
        y = data.get("y", 0.0)
        width = data.get("width", 1.0)
        height = data.get("height", 1.0)
        author = data.get("author", "")
        layer = data.get("layer", "images")
        locked = data.get("locked", False)
        if not all(isinstance(v, (int, float)) for v in (x, y, width, height)):
            raise ValueError("image x/y/width/height must be numbers")
        if float(width) <= 0 or float(height) <= 0:
            raise ValueError("image width/height must be positive")
        if not isinstance(author, str) or not isinstance(layer, str):
            raise ValueError("author/layer must be strings")
        if not isinstance(locked, bool):
            raise ValueError("locked must be a bool")
        return cls(
            image_id=image_id,
            asset_id=asset_id,
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
            author=author,
            layer=layer or "images",
            locked=locked,
        )


@dataclass(slots=True)
class Page:
    page_id: str
    width: float = 1280.0
    height: float = 800.0
    background: str = "#fafaf7"
    strokes: dict[str, Stroke] = field(default_factory=dict)
    stroke_order: list[str] = field(default_factory=list)
    images: dict[str, ImageObject] = field(default_factory=dict)
    image_order: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "page_id": self.page_id,
            "width": self.width,
            "height": self.height,
            "background": self.background,
            "stroke_order": list(self.stroke_order),
            "strokes": {sid: self.strokes[sid].to_dict() for sid in self.stroke_order},
            "image_order": list(self.image_order),
            "images": {iid: self.images[iid].to_dict() for iid in self.image_order},
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Page:
        page_id = data.get("page_id")
        if not isinstance(page_id, str) or page_id == "":
            raise ValueError("page_id must be a non-empty string")
        width = data.get("width", 1280.0)
        height = data.get("height", 800.0)
        background = data.get("background", "#fafaf7")
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            raise ValueError("page width/height must be numbers")
        if not isinstance(background, str) or background == "":
            raise ValueError("background must be a non-empty string")
        order_raw = data.get("stroke_order", [])
        strokes_raw = data.get("strokes", {})
        if not isinstance(order_raw, list) or not isinstance(strokes_raw, dict):
            raise ValueError("stroke_order/strokes invalid")
        strokes: dict[str, Stroke] = {}
        for key, value in strokes_raw.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                raise ValueError("invalid stroke entry")
            strokes[key] = Stroke.from_dict({str(k): v for k, v in value.items()})
        order: list[str] = []
        for item in order_raw:
            if not isinstance(item, str):
                raise ValueError("stroke_order entries must be strings")
            if item in strokes:
                order.append(item)
        for sid in strokes:
            if sid not in order:
                order.append(sid)

        image_order_raw = data.get("image_order", [])
        images_raw = data.get("images", {})
        if image_order_raw is None:
            image_order_raw = []
        if images_raw is None:
            images_raw = {}
        if not isinstance(image_order_raw, list) or not isinstance(images_raw, dict):
            raise ValueError("image_order/images invalid")
        images: dict[str, ImageObject] = {}
        for key, value in images_raw.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                raise ValueError("invalid image entry")
            images[key] = ImageObject.from_dict({str(k): v for k, v in value.items()})
        image_order: list[str] = []
        for item in image_order_raw:
            if not isinstance(item, str):
                raise ValueError("image_order entries must be strings")
            if item in images:
                image_order.append(item)
        for iid in images:
            if iid not in image_order:
                image_order.append(iid)

        return cls(
            page_id=page_id,
            width=float(width),
            height=float(height),
            background=background,
            strokes=strokes,
            stroke_order=order,
            images=images,
            image_order=image_order,
        )
