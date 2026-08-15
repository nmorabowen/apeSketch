# AProjects

Working memory for apeSketch. This folder is the project brain: why
decisions were made, what the product is, and how agents and humans
should continue.

Published user docs, when they exist, live under `docs/`. Code lives
under `src/`. **Facts about intent belong here**, not in chat logs.

| Folder | Holds |
|---|---|
| [`memory/`](memory/README.md) | Standing context: product intent, glossary, coupling |
| [`adrs/`](adrs/README.md) | Architecture Decision Records (append-only) |
| [`specs/`](specs/README.md) | Specifications for slices (document, ops, clients) |
| [`guides/`](guides/README.md) | How to work in this repo (agents and humans) |

## Rules

1. One fact, one home. If an ADR decides it, do not re-decide it in a spec.
2. ADRs are append-only. Amend with a new ADR; do not rewrite history.
3. Memory notes are living. ADRs are not.
4. Keep notes short. Link to ADRs instead of restating them.
5. Third-party whiteboards are **principle / pattern sources only**. Do
   not fork them as the apeSketch core ([ADR 0005](adrs/0005-own-core-adopt-patterns.md)).
