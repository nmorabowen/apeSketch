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


def test_pair_and_authorize() -> None:
    session = SketchSession()
    info = session.pair_info(host="192.168.1.10", port=9967)
    assert info["room"] == session.room_code
    assert "token=" in info["ws"]
    session.authorize(info["room"], session.token)
