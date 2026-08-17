# apeSketch

Hand-ink bridge for the ape* structural toolchain.

apeSketch is a **standalone Python library**. It records freehand
sketches (drawing tablet or Wi-Fi client), keeps a Session Document as
source of truth, and exports for agents and later apeCAD.

This repository is **public** (MIT). Status: pre-alpha — architecture under
[`AProjects/`](AProjects/README.md); prototype P0/P1 started.

## Locked decisions

| ADR | Decision |
|---|---|
| [0002](AProjects/adrs/0002-ink-bridge-scratchpad.md) | Ink bridge, not a whiteboard product |
| [0003](AProjects/adrs/0003-python-document-clients.md) | Python Document; clients emit Ops |
| [0004](AProjects/adrs/0004-lan-session-host.md) | LAN Session host; Wi-Fi Direct deferred |
| [0005](AProjects/adrs/0005-own-core-adopt-patterns.md) | Own core; adopt patterns / small MIT deps |

## Installation

```bash
pip install apeSketch
```

Then start a Session host:

```bash
python -m apeSketch
```

Opens a board on port **9966** (HTTP) with WebSocket on **9967**
(apeCAD uses 8765 — these stay separate). Pair page: `/pair`. Phone on
the same Wi‑Fi can open the advertised board URL.

HTTP-only (no WebSocket):

```bash
python -m apeSketch --http-only
```

From this checkout (shared OpenSees toolchain venv):

```powershell
C:\Users\nmb\venv\opensees_env\Scripts\python.exe -m pip install -e ".[dev]"
C:\Users\nmb\venv\opensees_env\Scripts\python.exe -m pytest
C:\Users\nmb\venv\opensees_env\Scripts\python.exe -m apeSketch
```

Do **not** rely on apeSketch’s local `.venv` for day-to-day work; keep deps in `opensees_env`.

## Layout

```
AProjects/           ADRs, memory, specs
src/apeSketch/       public Python package
  document.py        ink Document
  ops.py             typed Ops
  session.py         SketchSession
  host/              LAN HTTP + WS + static board
tests/
```

## Prototype plan

See [`AProjects/specs/prototype.md`](AProjects/specs/prototype.md).
