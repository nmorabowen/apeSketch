"""P0 Document / Ops tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apeSketch.document import Document
from apeSketch.errors import DocumentError
from apeSketch.export import page_to_svg
from apeSketch.ops import (
    SCHEMA_ID,
    AppendPoints,
    BeginStroke,
    ClearPage,
    EndStroke,
    EraseStroke,
    SetBackground,
)
from apeSketch.types import InkPoint, StrokeStyle


def _draw_stroke(doc: Document, stroke_id: str = "s1") -> None:
    doc.apply(
        BeginStroke(
            stroke_id=stroke_id,
            author="test",
            style=StrokeStyle(color="#222222", width=3),
        )
    )
    doc.apply(
        AppendPoints(
            stroke_id=stroke_id,
            points=(
                InkPoint(10, 10, 0.0, 0.4),
                InkPoint(20, 18, 16.0, 0.6),
                InkPoint(30, 12, 32.0, 0.5),
            ),
        )
    )
    doc.apply(EndStroke(stroke_id=stroke_id))


def test_begin_append_end_roundtrip(tmp_path: Path) -> None:
    doc = Document()
    _draw_stroke(doc)
    assert doc.revision == 3
    strokes = doc.strokes()
    assert len(strokes) == 1
    assert strokes[0].stroke_id == "s1"
    assert len(strokes[0].points) == 3
    assert strokes[0].open is False

    path = tmp_path / "demo.apesketch.json"
    doc.save(path)
    loaded = Document.load(path)
    assert loaded.revision == 3
    assert loaded.to_dict()["schema"] == SCHEMA_ID
    assert len(loaded.strokes()) == 1
    assert loaded.strokes()[0].points[1].x == 20


def test_snapshot_without_ops_log() -> None:
    doc = Document()
    _draw_stroke(doc)
    payload = doc.to_dict()
    del payload["ops"]
    restored = Document.from_dict(payload)
    assert len(restored.strokes()) == 1
    assert restored.revision == 3


def test_erase_and_clear() -> None:
    doc = Document()
    _draw_stroke(doc, "a")
    _draw_stroke(doc, "b")
    doc.apply(EraseStroke(stroke_id="a"))
    assert [s.stroke_id for s in doc.strokes()] == ["b"]
    doc.apply(ClearPage())
    assert doc.strokes() == []


def test_ink_kinds_and_background() -> None:
    doc = Document()
    assert doc.page().background == "#f4f0e6"
    doc.apply(SetBackground(color="#1c211c"))
    assert doc.page().background == "#1c211c"

    doc.apply(
        BeginStroke(
            stroke_id="chalk1",
            author="test",
            style=StrokeStyle(color="#ffffff", width=4, kind="chalk"),
        )
    )
    doc.apply(
        AppendPoints(
            stroke_id="chalk1",
            points=(InkPoint(0, 0, 0.0, 0.5), InkPoint(5, 5, 10.0, 0.8)),
        )
    )
    doc.apply(EndStroke(stroke_id="chalk1"))
    stroke = doc.strokes()[0]
    assert stroke.style.kind == "chalk"
    assert stroke.style.color == "#ffffff"

    svg = page_to_svg(doc.page())
    assert 'fill="#1c211c"' in svg
    assert 'data-kind="chalk"' in svg
    assert 'data-tip="round"' in svg

    payload = doc.to_dict()
    restored = Document.from_dict(payload)
    assert restored.page().background == "#1c211c"
    assert restored.strokes()[0].style.kind == "chalk"


def test_svg_pressure_varying_width() -> None:
    doc = Document()
    doc.apply(
        BeginStroke(
            stroke_id="press",
            author="t",
            style=StrokeStyle(color="#112233", width=2.0, kind="pen", tip="round"),
        )
    )
    doc.apply(
        AppendPoints(
            stroke_id="press",
            points=(
                InkPoint(0, 0, 0.0, 0.2),
                InkPoint(10, 0, 10.0, 0.9),
                InkPoint(20, 0, 20.0, 0.3),
            ),
        )
    )
    doc.apply(EndStroke(stroke_id="press"))
    svg = page_to_svg(doc.page())
    assert svg.count('data-stroke-id="press"') >= 2
    assert 'stroke-width="' in svg
    widths = []
    for part in svg.split("stroke-width=\"")[1:]:
        widths.append(float(part.split('"', 1)[0]))
    assert len(widths) >= 2
    assert max(widths) > min(widths)


def test_append_unknown_stroke_fails() -> None:
    doc = Document()
    with pytest.raises(DocumentError):
        doc.apply(
            AppendPoints(
                stroke_id="missing",
                points=(InkPoint(0, 0, 0.0),),
            )
        )


def test_add_and_replace_stroke_points() -> None:
    doc = Document()
    doc.apply_dict(
        {
            "op": "add_stroke",
            "stroke_id": "full",
            "author": "t",
            "points": [[0, 0, 0, 0.5], [10, 0, 1, 0.5], [20, 0, 2, 0.5], [30, 0, 3, 0.5]],
            "style": {"color": "#000000", "width": 2},
        }
    )
    assert len(doc.strokes()) == 1
    doc.apply_dict(
        {
            "op": "replace_stroke_points",
            "stroke_id": "full",
            "points": [[0, 0, 0, 0.5], [10, 0, 1, 0.5]],
        }
    )
    assert len(doc.strokes()[0].points) == 2
    doc.apply_dict({"op": "replace_stroke_points", "stroke_id": "full", "points": []})
    assert doc.strokes() == []


def test_apply_dict_and_agent_bundle(tmp_path: Path) -> None:
    doc = Document()
    doc.apply_dict(
        {
            "op": "begin_stroke",
            "stroke_id": "x",
            "author": "phone",
            "style": {"color": "#000000", "width": 2},
        }
    )
    doc.apply_dict(
        {
            "op": "append_points",
            "stroke_id": "x",
            "points": [[1, 2, 0, 0.5], [3, 4, 10, 0.7]],
        }
    )
    doc.apply_dict({"op": "end_stroke", "stroke_id": "x"})
    out = tmp_path / "bundle"
    manifest = doc.to_agent_bundle(out)
    assert manifest["stroke_count"] == 1
    assert (out / "ink.json").is_file()
    assert (out / "board.svg").is_file()
    ink = json.loads((out / "ink.json").read_text(encoding="utf-8"))
    assert ink["stroke_count"] == 1
