"""Ink Document. Mutate only through Ops; JSON replays the log."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apeSketch.errors import DocumentError
from apeSketch.ops import (
    SCHEMA_ID,
    UNITS,
    AppendPoints,
    BeginStroke,
    ClearPage,
    EndStroke,
    EraseStroke,
    Op,
    op_from_dict,
    op_to_dict,
)
from apeSketch.types import Page, Stroke, StrokeStyle


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

    def _clear_page(self, op: ClearPage) -> None:
        page = self._ensure_page(op.page_id)
        page.strokes.clear()
        page.stroke_order.clear()

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

    def to_agent_bundle(self, out_dir: str | Path) -> dict[str, Any]:
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
            "bounds": self._page_bounds(page),
        }
        ink_path.write_text(json.dumps(ink, indent=2), encoding="utf-8")
        svg_path.write_text(self._page_to_svg(page), encoding="utf-8")
        manifest = {
            "revision": self._revision,
            "page_id": page.page_id,
            "page_size": {"width": page.width, "height": page.height},
            "stroke_count": len(page.stroke_order),
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
        if not xs:
            return None
        return {
            "min_x": min(xs),
            "min_y": min(ys),
            "max_x": max(xs),
            "max_y": max(ys),
        }

    @staticmethod
    def _page_to_svg(page: Page) -> str:
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{page.width}" '
            f'height="{page.height}" viewBox="0 0 {page.width} {page.height}">',
            f'<rect width="100%" height="100%" fill="#f7f7f4"/>',
        ]
        for sid in page.stroke_order:
            stroke = page.strokes[sid]
            if len(stroke.points) == 0:
                continue
            d_parts: list[str] = []
            for i, point in enumerate(stroke.points):
                cmd = "M" if i == 0 else "L"
                d_parts.append(f"{cmd}{point.x:.2f},{point.y:.2f}")
            d = " ".join(d_parts)
            parts.append(
                f'<path data-stroke-id="{sid}" d="{d}" fill="none" '
                f'stroke="{stroke.style.color}" stroke-width="{stroke.style.width}" '
                f'stroke-linecap="round" stroke-linejoin="round"/>'
            )
        parts.append("</svg>")
        return "\n".join(parts)
