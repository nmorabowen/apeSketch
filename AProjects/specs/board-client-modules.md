# Spec — board client module split

**Status:** Planned (2026-08-20)
**ADRs:** 0005, 0009, 0010, 0011

## Goal

Decompose `host/static/board.js` (~6.5k-line IIFE) into native ES
modules with clear interfaces, without a bundler, without regressing
ink feel. The host already serves arbitrary static files (ADR 0011),
so new modules need no Python changes.

## Invariants (hold at every step)

- `window.__apeSketchBench` and `window.__apeSketchRules` stay
  assembled by the entry module — `scripts/bench_draw.mjs` and
  `scripts/bench_erase.mjs` are the regression net and must pass
  inside the ADR 0010 gates after **each** extraction.
- Document/ops wire format untouched; this is client-only.
- No build step: `<script type="module" src="/board.js">` plus plain
  `import` statements.

## Why not one big cut

The file's state is mutated through a small set of choke points
(`applyLocalOp`, `setTool`, style setters, cache invalidation), but
three knots block a naive split: the ~700-line pointer router touching
nine gesture objects, 40 DOM handles captured at file top, and
`drawOverlay` reaching into four subsystems. Cutting modules before
introducing façades produces circular imports.

## Order of operations

1. **Façades first, in place** (pure refactor, no file moves): create
   explicit objects inside the IIFE —
   `viewport` (view/dpr/coordinate math), `doc` (documentState +
   `applyLocalOp` + `getPage/getStroke/getImage/getText`),
   `renderCache` (dirty flags + bake layers + spatial index),
   `gestureCtx` (pointer/pinch/gesture state bag).
2. **Trivial extractions** to prove the plumbing: `geometry.js`
   (merge with `selection.js`), `recording.js`, `perf.js`
   (inject `getScene/getTool/getScale/getTier`).
3. **`brush.js` absorbs the ink engine** (`widthAtSample`,
   `synthesizeDisplayPoints`, `drawStrokePoints`, `applyTipCaps`,
   scratch buffers) — pure functions, highest test value.
4. **Medium seams:** `rule.js` (ADR 0009 subsystem — cleanest seam,
   ~97/123 refs already internal), `net.js` (ws + sync queue +
   `applyLocalOp` as a handler table), `sessions.js` (REST CRUD +
   snapshot apply), `text.js` (HTML↔block bridge; canvas layout may
   split further), `assets.js` (upload/import/export),
   `ui-docks.js` (one `makeDock()` factory replaces ~150 duplicated
   dock-controller lines).
5. **Renderer** (`renderer.js`): frame scheduling, live-stroke layer,
   bake/composite, grid, `drawOverlay` — callers pass an overlay
   descriptor (or register paint callbacks) so it stops reaching into
   selection/rule/text state.
6. **Pointer router last** (`input.js` + per-tool objects): split per
   tool once steps 1–5 removed its dependencies; each tool owns its
   gesture state; `input.js` owns pointers/pinch/pan and dispatches.

## Known duplication to retire along the way

- Two selection representations (`selectedIds` Set vs legacy
  `selectedImageId`/`selectedTextId` + `syncLegacySelectionIds`) —
  collapse to the Set.
- `normalizeCreateRect` vs `Sel.normalizeRect`; `drawPadlockAt` vs
  `drawLockIcon`; `decimateForCommit` vs `decimatePoints`;
  `avg`/`p95` ×3; inline blob-download vs `downloadBlob`;
  `projectOntoSegment`/`projectOntoLine` ~80% shared.
- Design tokens: `board.html` `:root` re-declares what
  `static/tokens.css` holds; link the stylesheet instead (it is
  reachable now that static serving is generic).

## Done when

`board.js` is an entry module (< ~300 lines: imports, wiring, bench
hooks) and every module above has a single responsibility; benches
green throughout.
