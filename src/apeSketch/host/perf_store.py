"""Append-only performance telemetry for local Session hosts."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Repo-local by default when running from a checkout; falls back under cwd.
DEFAULT_PERF_DIR = Path(".apeSketch") / "perf"
_lock = threading.Lock()


def perf_dir(root: Path | None = None, *, directory: Path | None = None) -> Path:
    if directory is not None:
        path = directory
    else:
        base = root if root is not None else Path.cwd()
        path = base / DEFAULT_PERF_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _day_file(directory: Path) -> Path:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    return directory / f"board-{day}.jsonl"


def append_sample(
    sample: dict[str, Any],
    *,
    root: Path | None = None,
    directory: Path | None = None,
) -> dict[str, Any]:
    """Append one telemetry sample. Returns storage metadata."""
    directory = perf_dir(root, directory=directory)
    path = _day_file(directory)
    record = {
        "received_at": datetime.now(UTC).isoformat(),
        **sample,
    }
    line = json.dumps(record, separators=(",", ":")) + "\n"
    with _lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    return {"ok": True, "path": str(path), "bytes": len(line)}


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def summarize(
    limit: int = 200,
    *,
    root: Path | None = None,
    directory: Path | None = None,
) -> dict[str, Any]:
    """Rolling summary over the newest samples in today's JSONL (and yesterday if thin)."""
    directory = perf_dir(root, directory=directory)
    files = sorted(directory.glob("board-*.jsonl"), reverse=True)
    rows: list[dict[str, Any]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                parsed: object = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append({str(k): v for k, v in parsed.items()})
        if len(rows) >= limit:
            break
    rows = rows[-limit:]

    def series(key: str) -> list[float]:
        out: list[float] = []
        for row in rows:
            timings = row.get("timings")
            if not isinstance(timings, dict):
                continue
            block = timings.get(key)
            if isinstance(block, dict):
                out.append(_safe_float(block.get("avg")))
            elif isinstance(block, (int, float)):
                out.append(float(block))
        return out

    def avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    fps = [_safe_float(row.get("fps")) for row in rows if row.get("fps") is not None]
    points = []
    strokes = []
    for row in rows:
        scene = row.get("scene")
        if isinstance(scene, dict):
            points.append(_safe_float(scene.get("points")))
            strokes.append(_safe_float(scene.get("strokes")))

    return {
        "sample_count": len(rows),
        "dir": str(directory),
        "fps_avg": avg(fps),
        "redraw_ms_avg": avg(series("redraw_ms")),
        "stamp_ms_avg": avg(series("stamp_ms")),
        "commit_ms_avg": avg(series("commit_ms")),
        "emit_ms_avg": avg(series("emit_ms")),
        "points_avg": avg(points),
        "strokes_avg": avg(strokes),
        "latest": rows[-1] if rows else None,
    }
