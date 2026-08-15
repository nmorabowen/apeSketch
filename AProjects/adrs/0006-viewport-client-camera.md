# ADR 0006 — Viewport pan/zoom is client camera, not Document state

**Status:** Accepted (2026-08-14)

## Context

The board needs infinite-canvas feel: zoom in/out, pan, and a background
grid that changes density with scale. Putting camera state into the Ops
log would fight multi-client sync (each device wants its own view) and
would bloat the ink Document.

apeCAD already treats navigation as client-only (view cube / camera not
in the ops log).

## Decision

- **Pan and zoom live only in the board client** (transform: offset +
  scale).
- Pointer input is converted to **world / Document coordinates** before
  Ops are sent.
- Background **grid step adapts to zoom** (1–2–5×10ⁿ minor lines; major
  every 5 minors). Origin axes are drawn as a light crosshair.
- Stroke geometry in `.apesketch.json` stays in world units; zoom does
  not rewrite points.

## Alternatives rejected

| Rejected | Why |
|---|---|
| Store camera in Document / Ops | Breaks per-client views; pollutes ink |
| Fixed page size with scrollbars only | Not an infinite board |
| Rasterize zoom into stroke widths on server | Wrong layer; hurts agent geometry |

## Consequences

Fit-to-content / shared “follow my view” would be a later, explicit
feature — not implied by this ADR. Agent exports render world space
(or a chosen crop), independent of any one client's zoom.
