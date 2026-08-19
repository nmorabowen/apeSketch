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
class TextRun:
    """Styled span inside a text block. Missing fields inherit box defaults."""

    text: str
    font_size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    color: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"text": self.text}
        if self.font_size is not None:
            payload["font_size"] = self.font_size
        if self.bold is not None:
            payload["bold"] = self.bold
        if self.italic is not None:
            payload["italic"] = self.italic
        if self.color is not None:
            payload["color"] = self.color
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TextRun:
        text = data.get("text", "")
        if not isinstance(text, str):
            raise ValueError("run text must be a string")
        font_size = data.get("font_size")
        bold = data.get("bold")
        italic = data.get("italic")
        color = data.get("color")
        fs: float | None
        if font_size is None:
            fs = None
        elif isinstance(font_size, (int, float)) and float(font_size) > 0:
            fs = float(font_size)
        else:
            raise ValueError("run font_size must be a positive number")
        if bold is not None and not isinstance(bold, bool):
            raise ValueError("run bold must be a bool")
        if italic is not None and not isinstance(italic, bool):
            raise ValueError("run italic must be a bool")
        if color is not None and (not isinstance(color, str) or color == ""):
            raise ValueError("run color must be a non-empty string")
        return cls(
            text=text,
            font_size=fs,
            bold=bold if isinstance(bold, bool) else None,
            italic=italic if isinstance(italic, bool) else None,
            color=color if isinstance(color, str) else None,
        )


@dataclass(slots=True)
class TextBlock:
    """One paragraph or list item inside a text box."""

    kind: str = "p"  # p | ul | ol
    indent: int = 0
    runs: list[TextRun] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "indent": self.indent,
            "runs": [run.to_dict() for run in self.runs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TextBlock:
        kind = data.get("kind", "p")
        indent = data.get("indent", 0)
        runs_raw = data.get("runs", [])
        if not isinstance(kind, str) or kind not in {"p", "ul", "ol"}:
            raise ValueError("block kind must be p, ul, or ol")
        if not isinstance(indent, int) or indent < 0 or indent > 6:
            raise ValueError("block indent must be an int 0..6")
        if not isinstance(runs_raw, list):
            raise ValueError("block runs must be a list")
        runs: list[TextRun] = []
        for item in runs_raw:
            if not isinstance(item, dict):
                raise ValueError("each run must be an object")
            runs.append(TextRun.from_dict({str(k): v for k, v in item.items()}))
        if not runs:
            runs = [TextRun(text="")]
        return cls(kind=kind, indent=indent, runs=runs)


def blocks_from_plain_content(content: str) -> list[TextBlock]:
    """Legacy plain content → one paragraph block per line."""
    lines = content.split("\n") if content else [""]
    return [TextBlock(kind="p", indent=0, runs=[TextRun(text=line)]) for line in lines]


def flatten_blocks(blocks: list[TextBlock]) -> str:
    lines: list[str] = []
    for block in blocks:
        lines.append("".join(run.text for run in block.runs))
    return "\n".join(lines)


def parse_blocks(raw: object | None, *, content: str = "") -> list[TextBlock]:
    if raw is None:
        return blocks_from_plain_content(content)
    if not isinstance(raw, list):
        raise ValueError("blocks must be a list")
    if not raw:
        return blocks_from_plain_content(content)
    blocks: list[TextBlock] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each block must be an object")
        blocks.append(TextBlock.from_dict({str(k): v for k, v in item.items()}))
    return blocks


@dataclass(slots=True)
class TextObject:
    """Text box on the page: geometry is a window; typography lives in blocks."""

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
    locked: bool = False
    blocks: list[TextBlock] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.blocks:
            self.blocks = blocks_from_plain_content(self.content)

    def to_dict(self) -> dict[str, object]:
        return {
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
            "locked": self.locked,
            "blocks": [block.to_dict() for block in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TextObject:
        text_id = data.get("text_id")
        content = data.get("content", "")
        if not isinstance(text_id, str) or text_id == "":
            raise ValueError("text_id must be a non-empty string")
        if not isinstance(content, str):
            raise ValueError("content must be a string")
        x = data.get("x", 0.0)
        y = data.get("y", 0.0)
        width = data.get("width", 200.0)
        height = data.get("height", 40.0)
        font_size = data.get("font_size", 28.0)
        color = data.get("color", "#111111")
        bold = data.get("bold", False)
        italic = data.get("italic", False)
        author = data.get("author", "")
        layer = data.get("layer", "text")
        locked = data.get("locked", False)
        if not all(isinstance(v, (int, float)) for v in (x, y, width, height, font_size)):
            raise ValueError("text geometry must be numbers")
        if float(width) <= 0 or float(height) <= 0 or float(font_size) <= 0:
            raise ValueError("text width/height/font_size must be positive")
        if not isinstance(color, str) or color == "":
            raise ValueError("color must be a non-empty string")
        if not isinstance(bold, bool) or not isinstance(italic, bool):
            raise ValueError("bold/italic must be bools")
        if not isinstance(author, str) or not isinstance(layer, str):
            raise ValueError("author/layer must be strings")
        if not isinstance(locked, bool):
            raise ValueError("locked must be a bool")
        blocks = parse_blocks(data.get("blocks"), content=content)
        return cls(
            text_id=text_id,
            content=content if content else flatten_blocks(blocks),
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
            font_size=float(font_size),
            color=color,
            bold=bold,
            italic=italic,
            author=author,
            layer=layer or "text",
            locked=locked,
            blocks=blocks,
        )


@dataclass(slots=True)
class Page:
    page_id: str
    width: float = 1280.0
    height: float = 800.0
    background: str = "#f4f0e6"
    strokes: dict[str, Stroke] = field(default_factory=dict)
    stroke_order: list[str] = field(default_factory=list)
    images: dict[str, ImageObject] = field(default_factory=dict)
    image_order: list[str] = field(default_factory=list)
    texts: dict[str, TextObject] = field(default_factory=dict)
    text_order: list[str] = field(default_factory=list)

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
            "text_order": list(self.text_order),
            "texts": {tid: self.texts[tid].to_dict() for tid in self.text_order},
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Page:
        page_id = data.get("page_id")
        if not isinstance(page_id, str) or page_id == "":
            raise ValueError("page_id must be a non-empty string")
        width = data.get("width", 1280.0)
        height = data.get("height", 800.0)
        background = data.get("background", "#f4f0e6")
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

        text_order_raw = data.get("text_order", [])
        texts_raw = data.get("texts", {})
        if text_order_raw is None:
            text_order_raw = []
        if texts_raw is None:
            texts_raw = {}
        if not isinstance(text_order_raw, list) or not isinstance(texts_raw, dict):
            raise ValueError("text_order/texts invalid")
        texts: dict[str, TextObject] = {}
        for key, value in texts_raw.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                raise ValueError("invalid text entry")
            texts[key] = TextObject.from_dict({str(k): v for k, v in value.items()})
        text_order: list[str] = []
        for item in text_order_raw:
            if not isinstance(item, str):
                raise ValueError("text_order entries must be strings")
            if item in texts:
                text_order.append(item)
        for tid in texts:
            if tid not in text_order:
                text_order.append(tid)

        return cls(
            page_id=page_id,
            width=float(width),
            height=float(height),
            background=background,
            strokes=strokes,
            stroke_order=order,
            images=images,
            image_order=image_order,
            texts=texts,
            text_order=text_order,
        )
