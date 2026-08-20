# Architecture Decision Records

Each ADR captures one significant decision: **context**, **decision**,
**alternatives rejected**, and **consequences**.

ADRs are append-only. If a later decision reverses or amends an earlier
one, write a new ADR that supersedes it; do not edit history.

Status: `Proposed` → `Accepted` → `Amended` / `Superseded`.

| # | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions in AProjects | Accepted |
| [0002](0002-ink-bridge-scratchpad.md) | apeSketch is an ink bridge, not a whiteboard product | Accepted |
| [0003](0003-python-document-clients.md) | Python Document is the language; Android and desktop are clients | Accepted |
| [0004](0004-lan-session-host.md) | Workstation hosts the session over LAN WebSocket; Wi-Fi Direct deferred | Accepted |
| [0005](0005-own-core-adopt-patterns.md) | Own core; adopt patterns / small MIT deps | Accepted |
| [0006](0006-viewport-client-camera.md) | Viewport pan/zoom is client camera, not Document state | Accepted |
| [0007](0007-instance-scoped-host.md) | Session host is instance-scoped, not machine-global | Accepted |
| [0008](0008-ape-json-substrate.md) | Consolidated `.ape.json` substrate across ape* documents | Accepted |
| [0009](0009-drawing-rules-client-capture.md) | Drawing rules are per-client capture aids, not Document state | Accepted |
| [0010](0010-ink-quality-tier.md) | Ink quality stays on Canvas 2D stack (Tier A) | Accepted |
| [0011](0011-library-layout-organic-growth.md) | Library layout for organic growth | Proposed |

## Template

```markdown
# ADR NNNN — short title

**Status:** Proposed | Accepted (YYYY-MM-DD)

## Context

What was at stake.

## Decision

What we chose.

## Alternatives rejected

| Rejected | Why |
|---|---|
| … | … |

## Consequences

What this forces on the code and on later ADRs.
```
