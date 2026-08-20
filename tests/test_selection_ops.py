"""Selection-related Ops: move strokes, set stroke style."""

from __future__ import annotations

import pytest
from tests.test_document import _draw_stroke

from apeSketch.document import Document
from apeSketch.errors import DocumentError
from apeSketch.ops import MoveStrokes, SetStrokeStyle, op_from_dict, op_to_dict


def test_move_strokes_translates_points() -> None:
    doc = Document()
    _draw_stroke(doc, "s1")
    doc.apply(MoveStrokes(stroke_ids=("s1",), dx=5.0, dy=-3.0))
    stroke = doc.strokes()[0]
    assert stroke.points[0].x == 15
    assert stroke.points[0].y == 7


def test_move_strokes_batch() -> None:
    doc = Document()
    _draw_stroke(doc, "a")
    _draw_stroke(doc, "b")
    doc.apply(MoveStrokes(stroke_ids=("a", "b"), dx=1.0, dy=2.0))
    assert doc.strokes()[0].points[0].y == 12


def test_move_strokes_unknown_raises() -> None:
    doc = Document()
    with pytest.raises(DocumentError, match="unknown stroke"):
        doc.apply(MoveStrokes(stroke_ids=("missing",), dx=1.0, dy=1.0))


def test_set_stroke_style_color_and_width() -> None:
    doc = Document()
    _draw_stroke(doc, "s1")
    doc.apply(SetStrokeStyle(stroke_ids=("s1",), color="#ff0000", width=6.0))
    style = doc.strokes()[0].style
    assert style.color == "#ff0000"
    assert style.width == 6.0


def test_set_stroke_style_partial() -> None:
    doc = Document()
    _draw_stroke(doc, "s1")
    orig_width = doc.strokes()[0].style.width
    doc.apply(SetStrokeStyle(stroke_ids=("s1",), color="#00ff00"))
    assert doc.strokes()[0].style.color == "#00ff00"
    assert doc.strokes()[0].style.width == orig_width


def test_selection_ops_json_roundtrip() -> None:
    move = MoveStrokes(stroke_ids=("s1", "s2"), dx=2.5, dy=-1.0)
    style = SetStrokeStyle(stroke_ids=("s1",), color="#abc", width=4.0)
    assert op_from_dict(op_to_dict(move)) == move
    restored = op_from_dict(op_to_dict(style))
    assert restored.stroke_ids == style.stroke_ids
