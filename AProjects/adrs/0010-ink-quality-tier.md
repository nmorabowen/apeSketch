# ADR 0010 — Ink quality stays on the current Canvas stack (Tier A)

**Status:** Accepted (2026-08-19)

## Context

Stylus pressure was already stored on every sample, but the board felt
thin compared with native drawing apps: one Pointer Event per frame,
full-scene redraws while inking, distance-only thinning, and straight
segments. We considered a WebGL stamp engine or waiting for the native
Android client (P4) before investing in feel.

apeSketch remains an ink **bridge** (ADR 0002), not an illustration
product. Feel still matters: agents and humans look at the same strokes.

## Decision

1. **Stay on Canvas 2D + vanilla `board.js` + Python Document.** Do not
   add a GPU ink engine until measurements show the browser is the
   ceiling.
2. **Tier A (this tree):** coalesced Pointer Events, packed open-stroke
   buffer, pressure-aware commit decimation, dedicated live-stroke layer,
   display-only spline / velocity / fountain inertia / short prediction.
   Document/ops stay raw `[x, y, t, pressure]`.
3. **Tier B (later, still web):** stamp atlas, calibration UI, richer
   brushes — only after `scripts/bench_draw.mjs` shows Tier A is stable.
4. **Tier C (later):** native Android/iOS capture (existing P4). Required
   for Procreate-class latency on iPad; not a prerequisite for Tier A.

Quality gates for Tier A (headless draw bench, medium tier):

| Metric | Target |
|---|---|
| `live_stroke_ms` p95 | &lt; 4 ms |
| `input_to_glass_ms` p95 (first frame / base capture) | &lt; 25 ms |
| `coalesced_per_frame` (simulated) | &gt; 1 |

## Alternatives rejected

| Rejected | Why |
|---|---|
| WebGL / stamp engine now | Costly; Canvas 2D still has headroom |
| Native-only ink quality | Delays every capture client; Document already has pressure |
| Put splines in the Op log | Replay and agents should see captured samples; display can densify |

## Consequences

Tune feel in `host/static/brush.js`. Change capture/commit in `board.js`.
Do not widen `InkPoint` (tilt, twist) until a client actually captures it.
SVG export may stay per-segment pressure widths; canvas is the live truth.
