---
name: apesketch-board-feature
description: >
  Checklist for changing the apeSketch board client or its op vocabulary: a tool,
  gesture, dock, overlay, render or capture path in src/apeSketch/host/static/
  (board.js, board.html, brush.js, selection.js, pair.html), and any new or
  changed Op kind in src/apeSketch/ops/, the Document handler in document.py,
  or export.py. Use it before editing those files, and before claiming a board
  change works. Every item points to the ADR, spec or guide that explains it.
---

# Board feature or op — checklist

Read this before you change the board client (`src/apeSketch/host/static/`) or
the op vocabulary (`src/apeSketch/ops/`). Most of this repo's history is this
kind of work (ADR 0012). Each item names a file and a heading to read. The
reasoning lives there, not here.

## 1. Does it belong in the Document at all?

- [ ] Per-device view and capture state stays in the client. The ADRs have
      rejected putting it in the op log three times: ADR 0006, "Alternatives
      rejected" ("Store camera in Document / Ops"); ADR 0009 ("Rules as Document
      objects / Ops"); ADR 0010 ("Put splines in the Op log").
- [ ] Clients emit ops, and only the Session writes the Document. ADR 0003,
      "Decision", items 2 and 3. Don't keep a second store in `board.js`.
- [ ] Ops carry the raw samples `[x, y, t, pressure]`. Don't widen `InkPoint`
      until a client actually captures more. ADR 0010, "Consequences".
- [ ] Features are judged by capture, sync or agent bridges, not by whiteboard
      parity. ADR 0002, "Consequences". Shape tools are out: ADR 0009, "Not
      shape tools".

## 2. A new or changed op

- [ ] Follow `AProjects/guides/adding-an-op.md` in order, steps 1–7: the op
      class, export, the `_<kind>` handler, `SAMPLES`, the client, and SVG export.
- [ ] The op kind must not collide with a private `Document` name.
      adding-an-op.md, step 4 (the name is the dispatch).
- [ ] The wire format is locked by the round-trips in `tests/test_ops.py`.
      ADR 0011, "Consequences". The `.ape.json` envelope stays: ADR 0008,
      "Decision" item 3.
- [ ] The host uses only the public core API: `apeSketch.export`, never
      `Document._*`. ADR 0011, "Growth rules" item 2 (the pre-0011 host reached
      into `Document._page_to_svg`).

## 3. The client

- [ ] A new client module is just a file under `host/static/`. The host serves
      whitelisted extensions, so it needs no Python route. ADR 0011, "Growth
      rules" item 4. A new file extension needs an entry in `_STATIC_MIME` in
      `host/server.py`.
- [ ] Moving code out of `board.js`? Follow the "Order of operations" in
      `AProjects/specs/board-client-modules.md` and keep its "Invariants":
      `window.__apeSketchBench`, `window.__apeSketchRules`, no build step.
- [ ] Touching duplicated code? Retire it using that spec's "Known duplication
      to retire along the way". Don't add a third copy.
- [ ] No bundler and no framework. ADR 0011, "Alternatives rejected".
- [ ] Brush feel goes in `brush.js`, capture and commit in `board.js`. ADR 0010,
      "Consequences".
- [ ] Adding a dependency? Check its license. AGPL stays out: ADR 0005,
      "Consequences".
- [ ] A new concept gets a row in `AProjects/memory/glossary.md`
      (adding-an-op.md, step 6).

## 4. Verify, including by eye

- [ ] `ruff check src tests` stays at 0 and `pytest` passes. See `AGENTS.md`,
      "Test and lint". CI runs neither.
- [ ] If you touched the ink, erase or pan path, run both benches and stay
      inside the ADR 0010 gates (perf-profile.md, "Workflow while developing").
- [ ] **Look at it.** Green tests prove the Document, not the board. Start a
      scratch host from *this* tree (`AGENTS.md`, "Running the host", which
      covers `PYTHONPATH=src` and a fresh `--root`). Open the board and use the
      feature. Capture a screenshot before and after the change.
- [ ] Drive input for real: a pointer drag on the canvas draws a stroke. Check
      that `GET /api/snapshot` shows the op in the Document, and that a
      **second tab** on the same board shows it live.
- [ ] Inspect the screenshots for clipping, overlap, stale state after undo
      or reload, and focus. Read the console for errors. Confirm
      `window.__apeSketchBench` and `window.__apeSketchRules` still exist.
- [ ] Stop what you launched, by the PID in `<root>/host.json`, then delete
      the scratch root.
- [ ] In the PR's "Test plan", list what you ran and what you looked at.

Found a new trap? Write it where it belongs, then add one line here that points
to it.
