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
| [0005](0005-own-core-adopt-patterns.md) | Own Document + Op protocol; adopt patterns and small MIT deps | Accepted |

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
