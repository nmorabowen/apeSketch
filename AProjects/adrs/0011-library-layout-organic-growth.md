# ADR 0011 — Library layout for organic growth

**Status:** Proposed (2026-08-20) — merging this branch accepts it

## Context

The prototype grew feature by feature and the growth pressure now
concentrates in three places (churn since repo start confirms it):

1. **Op vocabulary.** 20 op kinds, but every new op had to edit two
   central ~250-line dispatch functions in `ops.py` (`op_to_dict`,
   `op_from_dict`) plus a 42-line isinstance chain in `document.py`.
2. **Host process.** `server.py` (930+ lines) mixed four concerns: HTTP
   routes, the WebSocket bridge, autosave, and the CLI lifecycle. It
   also reached into a *private* `Document._page_to_svg` for exports,
   and every static client file needed its own hand-written route.
3. **Board client.** `board.js` is a single ~6.5k-line IIFE. It cannot
   be split until the host can serve arbitrary static modules.

Rendering/egress (SVG, agent bundle) also lived inside `Document`,
coupling the pure op-log state machine to export formats.

## Decision

### Package layout

```
src/apeSketch/
  types.py        object model (points, strokes, images, text, pages)
  ops/            op vocabulary, one module per domain
    _base.py      registry + shared payload parsing helpers
    stroke.py  image.py  text.py  page.py
  document.py     op-log state machine (apply/serialize only)
  export.py       egress: page_to_svg, write_agent_bundle
  session.py      live Session authority (broadcast, auth)
  assets.py       binary asset store
  substrate.py    shared .ape.json conventions (future shared pkg)
  host/
    server.py     HTTP server + routes + autosave (+ main re-export)
    ws.py         WebSocket bridge
    cli.py        argparse, startup/attach/banner/shutdown
    instance.py  session_store.py  perf_store.py  qr_svg.py
    static/       board client (vanilla JS, no build step)
```

### Growth rules

1. **Ops are self-describing.** An op class declares `kind`,
   `to_dict`, `from_payload`, and registers itself (`@register`).
   There is no central dispatch to edit. `Document` handles kind
   `<kind>` in a method named `_<kind>` — the naming convention *is*
   the dispatch. Adding an op = op class + Document handler + tests
   (see `AProjects/guides/adding-an-op.md`). `tests/test_ops.py`
   requires a wire round-trip sample for every registered op.
2. **Core never imports host; host uses only public core API.**
   Export endpoints call `apeSketch.export`, never `Document._*`.
3. **One concern per module.** New HTTP endpoints go in
   `host/server.py` routes; WS protocol changes in `host/ws.py`; CLI
   flags in `host/cli.py`. When a module accumulates a second concern
   or a region only touched by unrelated changes, split it then — not
   speculatively.
4. **Static files are data, not routes.** The host serves any
   whitelisted-extension file under `host/static/` (traversal-safe,
   `no-store` for js/css/html). Adding a client module never touches
   Python.
5. **The board client decomposes into ES modules incrementally**,
   bench-gated, per `AProjects/specs/board-client-modules.md`. No
   bundler, no framework (ADR 0005, 0010 stand).
6. **Quality gates:** `ruff check src tests` stays at zero findings;
   `pytest` green; draw/erase benches inside the ADR 0010 gates.
   Pyright strict is aspirational (146 pre-existing errors); reduce
   opportunistically, do not add new ones.

## Alternatives rejected

| Rejected | Why |
|---|---|
| Keep central op dispatch | Every feature edits the same two ~250-line functions; merge magnet |
| Big-bang board.js rewrite / framework | Risk without a regression net beyond two benches; violates ADR 0005 spirit |
| FastAPI / Flask for the host | Route table still small; stdlib keeps zero-friction install (prototype spec) |
| Bundler (Vite/esbuild) for the client | Native ES modules + generic static route suffice; no Node toolchain for the host |
| Split `types.py` now | 8 cohesive classes, one concern (object model); split when a second concern appears |

## Consequences

- `apeSketch.host.server:main` remains the console entry point (thin
  re-export of `host.cli.main`); Workbench's `server.SESSIONS_DIR` /
  `server.ASSET_DIR` pre-assignment contract is preserved.
- The ops registry makes unknown-op failures a lookup miss instead of
  a fall-through; the round-trip test suite is the wire-format lock.
- `board.js` dead code (9 never-called functions) is gone; the module
  split proceeds stepwise under the client spec, with
  `window.__apeSketchBench` / `__apeSketchRules` preserved as the test
  surface throughout.
- SVG/bundle format changes now happen in `export.py` without touching
  document semantics — and vice versa.
