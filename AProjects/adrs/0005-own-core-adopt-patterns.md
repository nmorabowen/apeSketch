# ADR 0005 — Own Document + Op protocol; adopt patterns and small MIT deps

**Status:** Accepted (2026-08-14)

## Context

Investigation showed mature free whiteboards and several agent-canvas
experiments. Forking or vendoring a full product would lock apeSketch to
someone else’s scene graph and, in several cases, to AGPL or commercial
licenses (PenEcho AGPL, Drafft AGPL, tldraw production key).

We still should not reinvent stroke outline math or WebSocket rooms from
first principles. Flexibility for apeCAD and agents comes from **owning
the Document and Op protocol**, not from reimplementing every pixel of UX.

## Decision

### Own (implement in this tree)

- Ink **Document** and **Op** protocol (append / erase / snapshot / …)
- **SketchSession** and LAN Session host
- Agent export (`to_agent_bundle`: structured ink + raster) and later
  **apeCAD promote**
- Android capture client that emits **our** Ops
- Canonical `.apesketch.json`

### Adopt as dependencies or patterns (not as core)

| Source | Allowed use |
|---|---|
| **perfect-freehand** (MIT) | Dependency for pressure stroke outlines |
| **BooxDraw / Excalidraw-room** | Pairing and stateless-relay **patterns** only |
| **Pointer Events / Android MotionEvent** | Platform APIs for capture |
| **Universal Ink Model** | Optional interop export target later |
| **JSON Canvas 1.0** | Parallel format only; not freehand ink store |

### Do not vendor / fork as apeSketch core

| Project | Why blocked |
|---|---|
| Excalidraw (as Document authority) | Wrong model; we need stroke Ops → ape* |
| PenEcho, Drafft.ink | AGPL; product scope |
| tldraw | Production license key; not free for shipping core |
| Chili3D / similar CAD UIs | Wrong product; license risk (see apeCAD ADR 0007) |

apeSketch remains **MIT**. Inspiration of architecture does not grant
copying source. Agents must not paste AGPL or proprietary whiteboard
trees into this repository.

## Alternatives rejected

| Rejected | Why |
|---|---|
| Fork Excalidraw / AndroidDraw as the product | Scene graph becomes the source of truth; weak ape* bridges |
| Write every stroke-math and WS primitive from scratch | Wastes time; MIT libs and patterns already exist |
| Embed AGPL canvas inside MIT package | License infection of the ape* core |

## Consequences

Specs define Op messages and `.apesketch.json` before large UI work.
Third-party whiteboard repos are reference reading for humans writing
ADRs and guides — not implementation trees for codegen. New dependencies
need a license check; AGPL stays out of the kernel.
