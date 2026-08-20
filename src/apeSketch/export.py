"""Document egress: SVG render and the agent bundle.

Reading a Document into files for agents (and humans) lives here so the
Document itself stays a pure op-log state machine. The host's export
endpoints use these functions too — nothing outside this module should
build SVG by hand.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apeSketch.ops import SCHEMA_ID, UNITS
from apeSketch.types import Page, Stroke, parse_blocks

if TYPE_CHECKING:
    from apeSketch.document import Document


def page_bounds(page: Page) -> dict[str, float] | None:
    """Tight bounding box over strokes, images, and texts; None when empty."""
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


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def page_to_svg(page: Page, *, assets: Any | None = None) -> str:
    """Render one page as standalone SVG.

    ``assets`` may provide ``data_uri(asset_id)`` to inline images;
    otherwise image hrefs point at the host's ``/api/asset/`` route.
    """
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
                    f"{_xml_escape(marker)}</text>"
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
                    f"{_xml_escape(run.text)}</text>"
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
        _append_stroke_svg(parts, sid, stroke)
    parts.append("</svg>")
    return "\n".join(parts)


def _width_at_pressure(base_width: float, pressure: float, kind: str, tip: str) -> float:
    p = max(0.0, min(1.0, pressure))
    if kind == "fountain":
        return base_width * (0.45 + p * 1.8)
    if kind == "chalk":
        return base_width * (0.55 + p * 1.05) * 1.7
    if tip == "chisel":
        return base_width * (0.5 + p * 1.0)
    if tip == "square":
        return base_width * (0.4 + p * 1.2)
    return base_width * (0.35 + p * 1.3)


def _append_stroke_svg(parts: list[str], sid: str, stroke: Stroke) -> None:
    tip = stroke.style.tip if stroke.style.tip in {"round", "square", "chisel"} else "round"
    kind = stroke.style.kind or "pen"
    opacity = "0.7" if kind == "chalk" else "1"
    linecap = "butt" if tip == "chisel" else ("square" if tip == "square" else "round")
    linejoin = "miter" if tip == "square" else "round"
    pressures = [pt.pressure for pt in stroke.points]
    varying = any(abs(p - pressures[0]) > 0.02 for p in pressures[1:]) if pressures else False
    if not varying or len(stroke.points) < 2:
        d_parts: list[str] = []
        for i, point in enumerate(stroke.points):
            cmd = "M" if i == 0 else "L"
            d_parts.append(f"{cmd}{point.x:.2f},{point.y:.2f}")
        width = _width_at_pressure(
            stroke.style.width, pressures[0] if pressures else 0.5, kind, tip
        )
        if kind == "chalk" and not varying:
            width = stroke.style.width * 1.6
        parts.append(
            f'<path data-stroke-id="{sid}" data-kind="{kind}" '
            f'data-tip="{tip}" d="{" ".join(d_parts)}" '
            f'fill="none" stroke="{stroke.style.color}" stroke-width="{width:.3f}" '
            f'stroke-opacity="{opacity}" '
            f'stroke-linecap="{linecap}" stroke-linejoin="{linejoin}"/>'
        )
        return
    for i in range(1, len(stroke.points)):
        a = stroke.points[i - 1]
        b = stroke.points[i]
        mid_p = (a.pressure + b.pressure) * 0.5
        width = _width_at_pressure(stroke.style.width, mid_p, kind, tip)
        if tip == "chisel":
            dx = b.x - a.x
            dy = b.y - a.y
            length = math.hypot(dx, dy) or 1.0
            nx = (-dy / length) * width * 0.55
            ny = (dx / length) * width * 0.55
            parts.append(
                f'<path data-stroke-id="{sid}" data-kind="{kind}" data-tip="{tip}" '
                f'd="M{a.x - nx:.2f},{a.y - ny:.2f} L{a.x + nx:.2f},{a.y + ny:.2f} '
                f'L{b.x + nx:.2f},{b.y + ny:.2f} L{b.x - nx:.2f},{b.y - ny:.2f} Z" '
                f'fill="{stroke.style.color}" stroke="none" fill-opacity="{opacity}"/>'
            )
        else:
            parts.append(
                f'<path data-stroke-id="{sid}" data-kind="{kind}" data-tip="{tip}" '
                f'd="M{a.x:.2f},{a.y:.2f} L{b.x:.2f},{b.y:.2f}" '
                f'fill="none" stroke="{stroke.style.color}" stroke-width="{width:.3f}" '
                f'stroke-opacity="{opacity}" '
                f'stroke-linecap="{linecap}" stroke-linejoin="{linejoin}"/>'
            )


def write_agent_bundle(
    document: Document, out_dir: str | Path, *, assets: Any | None = None
) -> dict[str, Any]:
    """Write structured ink for agents. SVG stand-in until PNG render lands."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    page = document.page()
    ink_path = out / "ink.json"
    svg_path = out / "board.svg"
    manifest_path = out / "manifest.json"

    ink = {
        "schema": SCHEMA_ID,
        "units": UNITS,
        "revision": document.revision,
        "page": page.to_dict(),
        "stroke_count": len(page.stroke_order),
        "image_count": len(page.image_order),
        "bounds": page_bounds(page),
    }
    ink_path.write_text(json.dumps(ink, indent=2), encoding="utf-8")
    svg_path.write_text(page_to_svg(page, assets=assets), encoding="utf-8")
    manifest = {
        "revision": document.revision,
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
