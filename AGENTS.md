# apeSketch — working rules for agents

apeSketch is a standalone MIT Python library: an ink bridge from a tablet or
browser board to a Python Session Document that agents and apeCAD read. What it
is and is not: [`AProjects/memory/intent.md`](AProjects/memory/intent.md).
The default branch is **`master`**, not `main`.

This file is a map. It routes to the docs that hold the facts and does not
restate them. `AProjects/` holds the project's knowledge (ADR 0001). Read
[`AProjects/README.md`](AProjects/README.md), then the
[ADR index](AProjects/adrs/README.md). ADRs are append-only. To reverse a
decision, write a new ADR; do not edit the old one.

## Task guides — read the matching one before starting

| Doing this | Read first |
|---|---|
| Changing the board client (`src/apeSketch/host/static/`) or adding/changing an op | [`.claude/skills/apesketch-board-feature/SKILL.md`](.claude/skills/apesketch-board-feature/SKILL.md) |
| Adding an op (the step-by-step procedure) | [`AProjects/guides/adding-an-op.md`](AProjects/guides/adding-an-op.md) |
| Anything that can change ink, erase or pan speed | [`AProjects/guides/perf-profile.md`](AProjects/guides/perf-profile.md) |
| Choosing a Python environment | [`AProjects/guides/python-env.md`](AProjects/guides/python-env.md) |

The guide is a checklist that points into the ADRs, specs and guides. When you
learn a new trap, write it where it belongs (an ADR if it decides something, a
guide or memory note otherwise), then add one line to the guide pointing to it.

## Test and lint

Use the shared `opensees_env` venv, not a repo-local `.venv`
([python-env.md](AProjects/guides/python-env.md)). Run these from the checkout root:

```powershell
python -m pytest -q             # the suite
python -m ruff check src tests  # must stay at 0 findings (ADR 0011, growth rule 6)
python -m pyright               # strict, src/ only; errors already exist. Add no new ones
```

Traps:

1. **Your code isn't the code that gets imported.** The venv has an editable
   install of the main checkout. Only `pytest` puts this tree's `src/` first
   (`pythonpath` in `pyproject.toml`, PR #11). Everything else, including
   `python -m apeSketch`, runs the **main checkout**, unless you set
   `PYTHONPATH=src`. Never run `pip install -e .` from a worktree. See
   python-env.md, "Worktrees and editable installs".
2. **CI runs no tests.** `.github/workflows/` has only `pages.yml` (deploys
   `docs/`) and `publish.yml` (PyPI on a GitHub release). The commands above
   are the only gate, so run them.
3. `ruff check .` also reports 2 old `E501` errors in `assets/logo/build.py`.
   That file is outside the gate. The gate is `ruff check src tests`.
4. Measure the pyright count before and after your change. The baseline is in
   ADR 0012, "Results".

## Running the host

```powershell
$env:PYTHONPATH = "src"   # trap 1: otherwise you run the main checkout
python -m apeSketch --root <scratch-dir> --port 0 --no-browser
```

- Pass a **fresh scratch `--root`**. Each instance root gets its own host
  (ADR 0007). The default root is `./.apeSketch` in the current directory, and
  it holds real sessions.
- ADR 0007 says starting a root whose host is still alive attaches to that host.
  **On Windows it does not today.** It starts a second host on the same root and
  overwrites `host.json` (ADR 0012, "Found while verifying"). Don't depend on
  attach.
- `<root>/host.json` records the `pid` and the ports. Stop what you started by
  that PID (`Stop-Process -Id <pid>` / `taskkill /PID <pid> /F`). A forced kill
  leaves `host.json` and autosaved sessions behind, so delete the scratch root.
- Ports 9966/9967 are only the preferred defaults, not the host's identity.
  apeCAD uses 8765.
- The draw and erase benches (`scripts/bench_*.mjs`) need Playwright
  (`npm install`) and a host on port 9972 or on `APESKETCH_PORT`. The gates are
  in ADR 0010. Details: perf-profile.md.

## Where things live

- Package layout and growth rules: [ADR 0011](AProjects/adrs/0011-library-layout-organic-growth.md).
  It is not restated here, so read it before adding a module.
- `AProjects/adrs/`: decisions, as `NNNN-kebab-title.md`, each with a row in
  the index. `specs/`: slice specs, written only once an ADR has locked the
  decision. `memory/`: living context. `guides/`: how to work in the repo.
- A plan for a change is an ADR (Context / Decision / Alternatives rejected /
  Consequences; template in the ADR index).
- **`docs/` is the public GitHub Pages site**, redeployed on every push to
  `master`. Working notes never go there (ADR 0001).
- `.claude/skills/` holds the task guides and is tracked. The rest of
  `.claude/` (worktrees, local settings) is ignored.

## Cross-repo contracts

- **Workbench / Habitat** bind an instance with `--root` / `--sessions` /
  `--assets` and read `GET /api/host` (ADR 0007). Workbench may assign
  `server.SESSIONS_DIR` / `server.ASSET_DIR` before `main()`. Keep that
  contract (ADR 0011, "Consequences"; `host/cli.py`).
- **apeCAD** shares the `.ape.json` envelope, routed by the `schema` field
  (ADR 0008).
- The full map is in [`AProjects/memory/coupling.md`](AProjects/memory/coupling.md).

## PRs and branches

- Base every PR on `master`. The global "`--base main`" advice means
  `--base master` in this repo.
- Branch names used so far: `feature/<slug>`, `fix/<slug>`, `claude/<slug>`.
- A PR body has a **Summary** and a **Test plan**. The test plan lists what you
  ran, with counts, and what you checked by eye.
- A release is a GitHub release. `publish.yml` pushes it to PyPI through
  Trusted Publishing. The version lives in `pyproject.toml`.
