"""Session authority tests."""

from __future__ import annotations

from apeSketch.ops import AppendPoints, BeginStroke, EndStroke
from apeSketch.session import SketchSession
from apeSketch.types import InkPoint


def test_session_broadcasts_ops() -> None:
    session = SketchSession()
    seen: list[dict] = []
    session.subscribe(seen.append)
    session.apply(BeginStroke(stroke_id="s1", author="a"))
    session.apply(
        AppendPoints(stroke_id="s1", points=(InkPoint(1, 1, 0.0), InkPoint(2, 2, 1.0)))
    )
    session.apply(EndStroke(stroke_id="s1"))
    assert len(seen) == 3
    assert seen[-1]["type"] == "op"
    assert seen[-1]["rev"] == 3
    assert len(session.document.strokes()) == 1


def test_session_apply_many_dicts() -> None:
    session = SketchSession()
    seen: list[dict] = []
    session.subscribe(seen.append)
    message = session.apply_many_dicts(
        [
            {"op": "begin_stroke", "stroke_id": "b1", "author": "a"},
            {
                "op": "append_points",
                "stroke_id": "b1",
                "points": [[1, 1, 0, 0.5], [4, 5, 10, 0.5]],
            },
            {"op": "end_stroke", "stroke_id": "b1"},
        ]
    )
    assert message["type"] == "ops"
    assert len(message["ops"]) == 3
    # Fan-out as individual op messages so older clients stay in sync.
    assert len(seen) == 3
    assert all(item["type"] == "op" for item in seen)
    assert len(session.document.strokes()) == 1


def test_pair_and_authorize() -> None:
    session = SketchSession()
    info = session.pair_info(host="192.168.1.10", port=9967)
    assert info["room"] == session.room_code
    assert "token=" in info["ws"]
    session.authorize(info["room"], session.token)
