# ADR 0002 — apeSketch is an ink bridge, not a whiteboard product

**Status:** Accepted (2026-08-14)

## Context

The ape* toolchain already has apeCAD as a spatial intent scratchpad
(points, lines, boxes → frame graph). We also need a place to capture
**hand-drawn ideas** — from a drawing tablet or a Wi-Fi Android tablet —
and make them durable for **agentic consumption** and later promote into
apeCAD.

Open-source whiteboards (Excalidraw, PenEcho, Drafft, tldraw) already
cover general drawing UIs. Competing with them as a product is the wrong
job. The gap is a small library whose document is the language, with
thin capture clients and explicit exports for agents.

## Decision

apeSketch is a **standalone MIT Python library** that:

1. Records freehand ink as a typed **Document** (strokes with stable IDs,
   timing, pressure, layers).
2. Acts as a **bridge**: capture → persist → expose to agents and to
   apeCAD.
3. Always supports **dual egress** for agents: structured ink JSON and
   on-demand PNG/SVG (vision).
4. Is **not** a SolidWorks clone, not a second Excalidraw, and not a
   chat UI.

Canonical on-disk form is `.apesketch.json` (schema frozen in a later
spec ADR). Optional promote path: ink regions → apeCAD ops.

## Alternatives rejected

| Rejected | Why |
|---|---|
| Ship a full collaborative whiteboard product | Wrong scope; duplicates Excalidraw-class apps |
| Raster-only capture (PNG boards) | Loses addressable strokes for agents and edit |
| Merge ink into apeCAD Document | Confuses pre-geometry ink with typed spatial intent |
| TypeScript-only SDK as the product | Splits agents and ape* Python bridges |

## Consequences

UI clients exist to emit ops at the Document. Downstream libraries
consume exports; they do not own the ink store. Features are judged by
whether they improve capture, session sync, or agent/apeCAD bridges —
not by whiteboard feature parity.
