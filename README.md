<p align="center">
  <img src="assets/logo/lockup-horizontal.png" width="720" alt="apeSketch — ink bridge">
</p>

<p align="center">
  <strong>Hand-ink bridge for the ape* structural toolchain.</strong><br>
  Tablet in. Session Document out. Agents and apeCAD read the same page.
</p>

<p align="center">
  <a href="https://nmorabowen.github.io/apeSketch/">Site</a>
  ·
  <a href="AProjects/">AProjects</a>
  ·
  MIT · pre-alpha
</p>

---

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
| [0007](AProjects/adrs/0007-instance-scoped-host.md) | One host process per instance root; 9966 is a preferred port |

## Installation

```bash
pip install apeSketch
```

Then start a Session host:

```bash
python -m apeSketch
```

Opens a board on a **preferred** port **9966** (HTTP) with WebSocket on
**9967**. Those ports are a default, not machine identity: a second
instance (another `--root` or cwd) binds the next free pair. Pair page:
`/pair`. Phone on the same Wi‑Fi can open the advertised board URL.

The host is **instance-scoped** ([ADR 0007](AProjects/adrs/0007-instance-scoped-host.md)).
Default instance root is `./.apeSketch` in the current working directory
(sessions, assets, perf, `host.json`). Point it at a work folder with:

```bash
python -m apeSketch --root path/to/instance
```

Workbench-shaped roots (`files/` + `pictures/`) use those folders.
Starting the same root again attaches to the live host.

HTTP-only (no WebSocket):

```bash
python -m apeSketch --http-only
```

Workbench (and any other host) can bind one instance to a folder:

```bash
python -m apeSketch --root <folder> --sessions <folder>/files --assets <folder>/pictures --http-only --no-browser
```

`GET /api/host` reports that binding; `host.json` is the live stamp.

From this checkout (shared OpenSees toolchain venv):

```powershell
C:\Users\nmb\venv\opensees_env\Scripts\python.exe -m pip install -e ".[dev]"
C:\Users\nmb\venv\opensees_env\Scripts\python.exe -m pytest
C:\Users\nmb\venv\opensees_env\Scripts\python.exe -m apeSketch
```

Do **not** rely on apeSketch’s local `.venv` for day-to-day work; keep deps in `opensees_env`.

## Layout

```
AProjects/           ADRs, memory, specs, guides
src/apeSketch/       public Python package
  types.py           object model (strokes, images, text, pages)
  ops/               typed Ops, one module per domain (self-registering)
  document.py        ink Document (op-log state machine)
  export.py          egress: SVG render + agent bundle
  session.py         SketchSession
  host/              server.py (HTTP) · ws.py (WebSocket) · cli.py · static/ board
docs/                GitHub Pages
tests/
```

Layout rules and growth conventions: [ADR 0011](AProjects/adrs/0011-library-layout-organic-growth.md)
and [`AProjects/guides/adding-an-op.md`](AProjects/guides/adding-an-op.md).

## Prototype plan

See [`AProjects/specs/prototype.md`](AProjects/specs/prototype.md).
