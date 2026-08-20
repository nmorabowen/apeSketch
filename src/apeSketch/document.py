"""Ink Document. Mutate only through Ops; JSON replays the log."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apeSketch.errors import DocumentError
from apeSketch.ops import (
    SCHEMA_ID,
    UNITS,
    AddImage,
    AddStroke,
    AddText,
    AppendPoints,
    BeginStroke,
    ClearPage,
    EndStroke,
    EraseImage,
    EraseStroke,
    EraseText,
    MoveStrokes,
    Op,
    ReplaceStrokePoints,
    SetBackground,
    SetImageLock,
    SetStrokeStyle,
    SetTextContent,
    SetTextLock,
    SetTextStyle,
    TransformImage,
    TransformText,
    op_from_dict,
    op_to_dict,
)
from apeSketch.types import (
    ImageObject,
    InkPoint,
    Page,
    Stroke,
    StrokeStyle,
    TextObject,
    flatten_blocks,
    parse_blocks,
)


class Document:
    """In-memory ink scratchpad. The ops log is the only writer."""

    def __init__(self, *, page_width: float = 1280.0, page_height: float = 800.0) -> None:
        self._ops: list[Op] = []
        self._pages: dict[str, Page] = {
            "p0": Page(page_id="p0", width=page_width, height=page_height),
        }
        self._active_page_id: str = "p0"
        self._revision: int = 0

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def active_page_id(self) -> str:
        return self._active_page_id

    def page(self, page_id: str | None = None) -> Page:
        pid = page_id or self._active_page_id
        try:
            return self._pages[pid]
        except KeyError as exc:
            raise DocumentError(f"unknown page {pid!r}") from exc

    def strokes(self, page_id: str | None = None) -> list[Stroke]:
        page = self.page(page_id)
        return [page.strokes[sid] for sid in page.stroke_order if sid in page.strokes]

    def apply(self, op: Op) -> None:
        self._apply_op(op, record=True)

    def apply_dict(self, data: dict[str, Any]) -> None:
        self.apply(op_from_dict(data))

    def _apply_op(self, op: Op, *, record: bool) -> None:
        if isinstance(op, BeginStroke):
            self._begin_stroke(op)
        elif isinstance(op, AppendPoints):
            self._append_points(op)
        elif isinstance(op, EndStroke):
            self._end_stroke(op)
        elif isinstance(op, EraseStroke):
            self._erase_stroke(op)
        elif isinstance(op, ClearPage):
            self._clear_page(op)
        elif isinstance(op, SetBackground):
            self._set_background(op)
        elif isinstance(op, AddStroke):
            self._add_stroke(op)
        elif isinstance(op, ReplaceStrokePoints):
            self._replace_stroke_points(op)
        elif isinstance(op, AddImage):
            self._add_image(op)
        elif isinstance(op, EraseImage):
            self._erase_image(op)
        elif isinstance(op, TransformImage):
            self._transform_image(op)
        elif isinstance(op, SetImageLock):
            self._set_image_lock(op)
        elif isinstance(op, AddText):
            self._add_text(op)
        elif isinstance(op, SetTextContent):
            self._set_text_content(op)
        elif isinstance(op, SetTextStyle):
            self._set_text_style(op)
        elif isinstance(op, TransformText):
            self._transform_text(op)
        elif isinstance(op, EraseText):
            self._erase_text(op)
        elif isinstance(op, SetTextLock):
            self._set_text_lock(op)
        elif isinstance(op, MoveStrokes):
            self._move_strokes(op)
        elif isinstance(op, SetStrokeStyle):
            self._set_stroke_style(op)
        else:
            raise DocumentError(f"unknown op type {type(op)!r}")
        if record:
            self._ops.append(op)
            self._revision += 1

    def _ensure_page(self, page_id: str) -> Page:
        page = self._pages.get(page_id)
        if page is None:
            page = Page(page_id=page_id)
            self._pages[page_id] = page
        return page

    def _begin_stroke(self, op: BeginStroke) -> None:
        page = self._ensure_page(op.page_id)
        if op.stroke_id in page.strokes:
            raise DocumentError(f"stroke {op.stroke_id!r} already exists")
        style = op.style if op.style is not None else StrokeStyle()
        stroke = Stroke(
            stroke_id=op.stroke_id,
            style=style,
            layer=op.layer,
            author=op.author,
            open=True,
        )
        page.strokes[op.stroke_id] = stroke
        page.stroke_order.append(op.stroke_id)

    def _append_points(self, op: AppendPoints) -> None:
        page = self._ensure_page(op.page_id)
        stroke = page.strokes.get(op.stroke_id)
        if stroke is None:
            raise DocumentError(f"unknown stroke {op.stroke_id!r}")
        if not stroke.open:
            raise DocumentError(f"stroke {op.stroke_id!r} is already ended")
        stroke.points.extend(op.points)

    def _end_stroke(self, op: EndStroke) -> None:
        page = self._ensure_page(op.page_id)
        stroke = page.strokes.get(op.stroke_id)
        if stroke is None:
            raise DocumentError(f"unknown stroke {op.stroke_id!r}")
        stroke.open = False

    def _erase_stroke(self, op: EraseStroke) -> None:
        page = self._ensure_page(op.page_id)
        if op.stroke_id not in page.strokes:
            raise DocumentError(f"unknown stroke {op.stroke_id!r}")
        del page.strokes[op.stroke_id]
        page.stroke_order = [sid for sid in page.stroke_order if sid != op.stroke_id]

    def _add_stroke(self, op: AddStroke) -> None:
        page = self._ensure_page(op.page_id)
        if op.stroke_id in page.strokes:
            raise DocumentError(f"stroke {op.stroke_id!r} already exists")
        style = op.style if op.style is not None else StrokeStyle()
        page.strokes[op.stroke_id] = Stroke(
            stroke_id=op.stroke_id,
            points=list(op.points),
            style=style,
            layer=op.layer,
            author=op.author,
            open=False,
        )
        page.stroke_order.append(op.stroke_id)

    def _replace_stroke_points(self, op: ReplaceStrokePoints) -> None:
        page = self._ensure_page(op.page_id)
        stroke = page.strokes.get(op.stroke_id)
        if stroke is None:
            raise DocumentError(f"unknown stroke {op.stroke_id!r}")
        if len(op.points) == 0:
            del page.strokes[op.stroke_id]
            page.stroke_order = [sid for sid in page.stroke_order if sid != op.stroke_id]
            return
        stroke.points = list(op.points)
        stroke.open = False

    def _clear_page(self, op: ClearPage) -> None:
        page = self._ensure_page(op.page_id)
        page.strokes.clear()
        page.stroke_order.clear()
        page.images.clear()
        page.image_order.clear()
        page.texts.clear()
        page.text_order.clear()

    def _set_background(self, op: SetBackground) -> None:
        page = self._ensure_page(op.page_id)
        page.background = op.color

    def _add_image(self, op: AddImage) -> None:
        page = self._ensure_page(op.page_id)
        if op.image_id in page.images:
            raise DocumentError(f"image {op.image_id!r} already exists")
        page.images[op.image_id] = ImageObject(
            image_id=op.image_id,
            asset_id=op.asset_id,
            x=op.x,
            y=op.y,
            width=op.width,
            height=op.height,
            author=op.author,
            layer=op.layer,
        )
        page.image_order.append(op.image_id)

    def _erase_image(self, op: EraseImage) -> None:
        page = self._ensure_page(op.page_id)
        if op.image_id not in page.images:
            raise DocumentError(f"unknown image {op.image_id!r}")
        del page.images[op.image_id]
        page.image_order = [iid for iid in page.image_order if iid != op.image_id]

    def _transform_image(self, op: TransformImage) -> None:
        page = self._ensure_page(op.page_id)
        image = page.images.get(op.image_id)
        if image is None:
            raise DocumentError(f"unknown image {op.image_id!r}")
        if image.locked:
            raise DocumentError(f"image {op.image_id!r} is locked")
        image.x = op.x
        image.y = op.y
        image.width = op.width
        image.height = op.height

    def _set_image_lock(self, op: SetImageLock) -> None:
        page = self._ensure_page(op.page_id)
        image = page.images.get(op.image_id)
        if image is None:
            raise DocumentError(f"unknown image {op.image_id!r}")
        image.locked = op.locked

    def _add_text(self, op: AddText) -> None:
        page = self._ensure_page(op.page_id)
        if op.text_id in page.texts:
            raise DocumentError(f"text {op.text_id!r} already exists")
        try:
            blocks = parse_blocks(
                list(op.blocks) if op.blocks is not None else None,
                content=op.content,
            )
        except ValueError as exc:
            raise DocumentError(str(exc)) from exc
        content = op.content if op.content else flatten_blocks(blocks)
        page.texts[op.text_id] = TextObject(
            text_id=op.text_id,
            content=content,
            x=op.x,
            y=op.y,
            width=op.width,
            height=op.height,
            font_size=op.font_size,
            color=op.color,
            bold=op.bold,
            italic=op.italic,
            author=op.author,
            layer=op.layer,
            blocks=blocks,
        )
        page.text_order.append(op.text_id)

    def _set_text_content(self, op: SetTextContent) -> None:
        page = self._ensure_page(op.page_id)
        text = page.texts.get(op.text_id)
        if text is None:
            raise DocumentError(f"unknown text {op.text_id!r}")
        if text.locked:
            raise DocumentError(f"text {op.text_id!r} is locked")
        try:
            blocks = parse_blocks(
                list(op.blocks) if op.blocks is not None else None,
                content=op.content,
            )
        except ValueError as exc:
            raise DocumentError(str(exc)) from exc
        text.blocks = blocks
        text.content = op.content if op.content else flatten_blocks(blocks)

    def _set_text_style(self, op: SetTextStyle) -> None:
        page = self._ensure_page(op.page_id)
        text = page.texts.get(op.text_id)
        if text is None:
            raise DocumentError(f"unknown text {op.text_id!r}")
        if text.locked:
            raise DocumentError(f"text {op.text_id!r} is locked")
        if op.font_size is not None:
            text.font_size = op.font_size
        if op.color is not None:
            text.color = op.color
        if op.bold is not None:
            text.bold = op.bold
        if op.italic is not None:
            text.italic = op.italic

    def _transform_text(self, op: TransformText) -> None:
        page = self._ensure_page(op.page_id)
        text = page.texts.get(op.text_id)
        if text is None:
            raise DocumentError(f"unknown text {op.text_id!r}")
        if text.locked:
            raise DocumentError(f"text {op.text_id!r} is locked")
        text.x = op.x
        text.y = op.y
        text.width = op.width
        text.height = op.height
        if op.font_size is not None:
            text.font_size = op.font_size

    def _erase_text(self, op: EraseText) -> None:
        page = self._ensure_page(op.page_id)
        if op.text_id not in page.texts:
            raise DocumentError(f"unknown text {op.text_id!r}")
        del page.texts[op.text_id]
        page.text_order = [tid for tid in page.text_order if tid != op.text_id]

    def _set_text_lock(self, op: SetTextLock) -> None:
        page = self._ensure_page(op.page_id)
        text = page.texts.get(op.text_id)
        if text is None:
            raise DocumentError(f"unknown text {op.text_id!r}")
        text.locked = op.locked

    def _move_strokes(self, op: MoveStrokes) -> None:
        page = self._ensure_page(op.page_id)
        for stroke_id in op.stroke_ids:
            stroke = page.strokes.get(stroke_id)
            if stroke is None:
                raise DocumentError(f"unknown stroke {stroke_id!r}")
            stroke.points = [
                InkPoint(p.x + op.dx, p.y + op.dy, p.t, p.pressure) for p in stroke.points
            ]

    def _set_stroke_style(self, op: SetStrokeStyle) -> None:
        page = self._ensure_page(op.page_id)
        for stroke_id in op.stroke_ids:
            stroke = page.strokes.get(stroke_id)
            if stroke is None:
                raise DocumentError(f"unknown stroke {stroke_id!r}")
            old = stroke.style
            stroke.style = StrokeStyle(
                color=op.color if op.color is not None else old.color,
                width=op.width if op.width is not None else old.width,
                kind=old.kind,
                tip=old.tip,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_ID,
            "units": UNITS,
            "revision": self._revision,
            "active_page_id": self._active_page_id,
            "pages": {pid: page.to_dict() for pid, page in self._pages.items()},
            "ops": [op_to_dict(op) for op in self._ops],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Document:
        schema = data.get("schema")
        if schema is not None and schema != SCHEMA_ID:
            raise DocumentError(f"unsupported schema {schema!r}")
        doc = cls()
        ops_raw = data.get("ops")
        if isinstance(ops_raw, list) and ops_raw:
            for item in ops_raw:
                if not isinstance(item, dict):
                    raise DocumentError("ops entries must be objects")
                doc.apply(op_from_dict({str(k): v for k, v in item.items()}))
            return doc

        # Snapshot without ops log: restore pages directly.
        pages_raw = data.get("pages")
        if not isinstance(pages_raw, dict):
            raise DocumentError("document needs ops or pages")
        doc._pages = {}
        for pid, page_data in pages_raw.items():
            if not isinstance(pid, str) or not isinstance(page_data, dict):
                raise DocumentError("invalid page entry")
            page = Page.from_dict({str(k): v for k, v in page_data.items()})
            doc._pages[pid] = page
        active = data.get("active_page_id", "p0")
        if not isinstance(active, str):
            raise DocumentError("active_page_id must be a string")
        if active not in doc._pages:
            raise DocumentError(f"active_page_id {active!r} missing")
        doc._active_page_id = active
        rev = data.get("revision", 0)
        if not isinstance(rev, int) or rev < 0:
            raise DocumentError("revision must be a non-negative int")
        doc._revision = rev
        doc._ops = []
        return doc

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, text: str) -> Document:
        parsed: object = json.loads(text)
        if not isinstance(parsed, dict):
            raise DocumentError("JSON root must be an object")
        return cls.from_dict({str(k): v for k, v in parsed.items()})

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Document:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    def to_agent_bundle(self, out_dir: str | Path, *, assets: Any | None = None) -> dict[str, Any]:
        """Write structured ink for agents. SVG stand-in until PNG render lands."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        page = self.page()
        ink_path = out / "ink.json"
        svg_path = out / "board.svg"
        manifest_path = out / "manifest.json"

        ink = {
            "schema": SCHEMA_ID,
            "units": UNITS,
            "revision": self._revision,
            "page": page.to_dict(),
            "stroke_count": len(page.stroke_order),
            "image_count": len(page.image_order),
            "bounds": self._page_bounds(page),
        }
        ink_path.write_text(json.dumps(ink, indent=2), encoding="utf-8")
        svg_path.write_text(self._page_to_svg(page, assets=assets), encoding="utf-8")
        manifest = {
            "revision": self._revision,
            "page_id": page.page_id,
            "page_size": {"width": page.width, "height": page.height},
            "stroke_count": len(page.stroke_order),
            "image_count": len(page.image_order),
            "ink": str(ink_path.name),
            "board": str(svg_path.name),
            "board_format": "svg",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    @staticmethod
    def _page_bounds(page: Page) -> dict[str, float] | None:
        xs: list[float] = []
        ys: list[float] = []
        for stroke in page.strokes.values():
            for point in stroke.points:
                xs.append(point.x)
                ys.append(point.y)
        for image in page.images.values():
            xs.extend([image.x, image.x + image.width])
            ys.extend([image.y, image.y + image.height])
        for text in page.texts.values():
            xs.extend([text.x, text.x + text.width])
            ys.extend([text.y, text.y + text.height])
        if not xs:
            return None
        return {
            "min_x": min(xs),
            "min_y": min(ys),
            "max_x": max(xs),
            "max_y": max(ys),
        }

    @staticmethod
    def _xml_escape(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    @staticmethod
    def _page_to_svg(page: Page, *, assets: Any | None = None) -> str:
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{page.width}" '
            f'height="{page.height}" viewBox="0 0 {page.width} {page.height}">',
            f'<rect width="100%" height="100%" fill="{page.background}"/>',
        ]
        for iid in page.image_order:
            image = page.images.get(iid)
            if image is None:
                continue
            href = None
            if assets is not None and hasattr(assets, "data_uri"):
                href = assets.data_uri(image.asset_id)
            if not href:
                href = f"/api/asset/{image.asset_id}"
            parts.append(
                f'<image data-image-id="{image.image_id}" data-asset-id="{image.asset_id}" '
                f'href="{href}" x="{image.x:.2f}" y="{image.y:.2f}" '
                f'width="{image.width:.2f}" height="{image.height:.2f}" '
                f'preserveAspectRatio="none"/>'
            )
        for tid in page.text_order:
            text = page.texts.get(tid)
            if text is None:
                continue
            blocks = text.blocks or parse_blocks(None, content=text.content)
            y_cursor = text.y + 4.0
            ol_counters: dict[int, int] = {}
            for block in blocks:
                indent_px = 18.0 * block.indent
                marker = ""
                if block.kind == "ul":
                    marker = "•"
                elif block.kind == "ol":
                    ol_counters[block.indent] = ol_counters.get(block.indent, 0) + 1
                    for deeper in [k for k in ol_counters if k > block.indent]:
                        del ol_counters[deeper]
                    marker = f"{ol_counters[block.indent]}."
                marker_w = 16.0 if marker else 0.0
                x0 = text.x + 4.0 + indent_px + marker_w
                # Simple single-line SVG rows per block (wrapped content as one tspan chain).
                default_size = text.font_size
                line_h = default_size * 1.25
                if marker:
                    parts.append(
                        f'<text data-text-id="{text.text_id}" x="{text.x + 4 + indent_px:.2f}" '
                        f'y="{y_cursor + default_size * 0.85:.2f}" fill="{text.color}" '
                        f'font-size="{default_size * 0.9:.2f}" '
                        f'font-family="Segoe UI, system-ui, sans-serif">'
                        f"{Document._xml_escape(marker)}</text>"
                    )
                x_run = x0
                for run in block.runs:
                    fs = run.font_size if run.font_size is not None else default_size
                    bold = text.bold if run.bold is None else run.bold
                    italic = text.italic if run.italic is None else run.italic
                    color = run.color if run.color is not None else text.color
                    parts.append(
                        f'<text data-text-id="{text.text_id}" x="{x_run:.2f}" '
                        f'y="{y_cursor + fs * 0.85:.2f}" fill="{color}" '
                        f'font-size="{fs:.2f}" '
                        f'font-weight="{"700" if bold else "400"}" '
                        f'font-style="{"italic" if italic else "normal"}" '
                        f'font-family="Segoe UI, system-ui, sans-serif">'
                        f"{Document._xml_escape(run.text)}</text>"
                    )
                    # Approximate advance for SVG (not exact); fine for export snapshot.
                    x_run += len(run.text) * fs * 0.55
                y_cursor += line_h
                if y_cursor > text.y + text.height:
                    break
        for sid in page.stroke_order:
            stroke = page.strokes[sid]
            if len(stroke.points) == 0:
                continue
            d_parts: list[str] = []
            for i, point in enumerate(stroke.points):
                cmd = "M" if i == 0 else "L"
                d_parts.append(f"{cmd}{point.x:.2f},{point.y:.2f}")
            d = " ".join(d_parts)
            opacity = "0.7" if stroke.style.kind == "chalk" else "1"
            width = stroke.style.width * (1.6 if stroke.style.kind == "chalk" else 1.0)
            tip = stroke.style.tip if stroke.style.tip in {"round", "square", "chisel"} else "round"
            linecap = "butt" if tip == "chisel" else ("square" if tip == "square" else "round")
            linejoin = "miter" if tip == "square" else "round"
            parts.append(
                f'<path data-stroke-id="{sid}" data-kind="{stroke.style.kind}" '
                f'data-tip="{tip}" d="{d}" '
                f'fill="none" stroke="{stroke.style.color}" stroke-width="{width}" '
                f'stroke-opacity="{opacity}" '
                f'stroke-linecap="{linecap}" stroke-linejoin="{linejoin}"/>'
            )
        parts.append("</svg>")
        return "\n".join(parts)
