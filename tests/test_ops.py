"""Wire-format round trips for every registered op."""

from __future__ import annotations

import pytest

from apeSketch.errors import DocumentError
from apeSketch.ops import (
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
from apeSketch.ops._base import REGISTRY
from apeSketch.types import InkPoint, StrokeStyle

POINTS = (InkPoint(1.0, 2.0, 0.0, 0.4), InkPoint(3.0, 4.0, 16.0, 0.9))
STYLE = StrokeStyle(color="#224466", width=3.5, kind="fountain", tip="chisel")

SAMPLES: list[Op] = [
    BeginStroke(stroke_id="s1", author="tablet", layer="ink", style=STYLE),
    AppendPoints(stroke_id="s1", points=POINTS),
    EndStroke(stroke_id="s1"),
    EraseStroke(stroke_id="s1"),
    ClearPage(),
    SetBackground(color="#101820"),
    AddStroke(stroke_id="s2", points=POINTS, author="pc", style=STYLE),
    ReplaceStrokePoints(stroke_id="s2", points=POINTS),
    AddImage(image_id="i1", asset_id="a1", x=10.0, y=20.0, width=30.0, height=40.0),
    EraseImage(image_id="i1"),
    TransformImage(image_id="i1", x=1.0, y=2.0, width=3.0, height=4.0),
    SetImageLock(image_id="i1", locked=True),
    AddText(text_id="t1", content="hola", x=5.0, y=6.0, width=100.0, height=40.0),
    SetTextContent(text_id="t1", content="adios"),
    SetTextStyle(text_id="t1", font_size=30.0, bold=True),
    TransformText(text_id="t1", x=1.0, y=2.0, width=90.0, height=35.0, font_size=22.0),
    EraseText(text_id="t1"),
    SetTextLock(text_id="t1", locked=False),
    MoveStrokes(stroke_ids=("s2",), dx=4.0, dy=-2.0),
    SetStrokeStyle(stroke_ids=("s2",), color="#ff0000", width=5.0),
]


def test_every_registered_kind_has_a_sample() -> None:
    sampled = {type(op) for op in SAMPLES}
    registered = set(REGISTRY.values())
    assert sampled == registered


@pytest.mark.parametrize("op", SAMPLES, ids=lambda op: op.kind)
def test_roundtrip(op: Op) -> None:
    payload = op_to_dict(op)
    assert payload["op"] == op.kind
    assert op_from_dict(payload) == op


def test_unknown_kind_rejected() -> None:
    with pytest.raises(DocumentError):
        op_from_dict({"op": "warp_reality"})


def test_non_op_payloads_rejected() -> None:
    with pytest.raises(DocumentError):
        op_from_dict({"op": 42})
    with pytest.raises(DocumentError):
        op_from_dict({"op": "begin_stroke", "page_id": 7})


def test_op_to_dict_rejects_foreign_objects() -> None:
    with pytest.raises(DocumentError):
        op_to_dict(object())  # type: ignore[arg-type]
