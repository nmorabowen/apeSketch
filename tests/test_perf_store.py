"""Tests for append-only perf store."""

from __future__ import annotations

from pathlib import Path

from apeSketch.host.perf_store import append_sample, summarize


def test_append_and_summarize(tmp_path: Path) -> None:
    sample = {
        "t": "2026-08-15T00:00:00Z",
        "fps": 60,
        "scene": {"strokes": 3, "points": 100},
        "timings": {
            "redraw_ms": {"avg": 1.5, "p95": 2.0, "n": 10, "last": 1.0},
            "stamp_ms": {"avg": 0.4, "p95": 0.8, "n": 5, "last": 0.3},
        },
    }
    meta = append_sample(sample, root=tmp_path)
    assert meta["ok"] is True
    path = Path(meta["path"])
    assert path.is_file()
    summary = summarize(root=tmp_path)
    assert summary["sample_count"] == 1
    assert summary["fps_avg"] == 60
    assert summary["redraw_ms_avg"] == 1.5
    assert summary["points_avg"] == 100
