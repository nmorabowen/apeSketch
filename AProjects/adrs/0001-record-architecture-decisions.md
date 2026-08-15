# ADR 0001 — Record architecture decisions in AProjects

**Status:** Accepted (2026-08-14)

## Context

apeSketch starts as an empty library next to apeCAD, apeSteel, and
apeGmsh. Design intent from early chats must not live only in
transcripts. apeCAD already proved that a root-level `AProjects/` home
keeps decisions reloadable for humans and agents.

## Decision

All project memory lives under **`AProjects/`** at the repository root:

- `AProjects/adrs/` — append-only Architecture Decision Records
- `AProjects/memory/` — living context (intent, glossary, coupling)
- `AProjects/specs/` — slice specifications
- `AProjects/guides/` — how to work in the repo

Number ADRs as `NNNN-kebab-title.md`. Keep an index in this folder's
`README.md`. Do not rewrite accepted ADRs; amend with a successor.

## Alternatives rejected

| Rejected | Why |
|---|---|
| ADRs under `src/apeSketch/` | Mixes installable code with design memory |
| `docs/` as the only home | Published docs and working memory have different audiences |
| Chat transcripts as memory | They are not reloadable, indexed, or append-only |

## Consequences

Agents and humans look in `AProjects/` first. Code changes that reverse
an ADR require a new ADR, not a silent edit.
