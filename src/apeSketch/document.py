"""Ink Document. Mutate only through Ops; JSON replays the log.

Each op kind ``<kind>`` is handled by a ``_<kind>`` method on Document;
``_apply_op`` dispatches by that naming convention. Adding an op means
one op class (in ``apeSketch.ops``) plus one handler method here.
"""

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
        kind = getattr(op, "kind", None)
        handler = getattr(self, f"_{kind}", None) if isinstance(kind, str) else None
        if handler is None or not callable(handler):
            raise DocumentError(f"unknown op type {type(op)!r}")
        handler(op)
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
        """Write structured ink for agents (see :mod:`apeSketch.export`)."""
        from apeSketch.export import write_agent_bundle

        return write_agent_bundle(self, out_dir, assets=assets)
