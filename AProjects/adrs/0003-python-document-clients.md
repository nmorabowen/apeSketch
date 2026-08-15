# ADR 0003 — Python Document is the language; Android and desktop are clients

**Status:** Accepted (2026-08-14)

## Context

apeCAD decided that the Python document is the public language and the
web GUI is a client (apeCAD ADR 0003). apeSketch has the same audience:
coding agents, apeCAD, and humans at a desk. An Android app is required
for comfortable stylus capture, but it must not become a second source
of truth.

## Decision

Split the stack:

1. **Public authoring / session language = Python 3.11+.** The Document,
   Op API, Session, and bridges live in `src/apeSketch/`. Agents and
   ape* code speak this package.
2. **Clients emit Ops; they do not own the Document.**
   - Desktop scratchpad (web or otherwise) is a client.
   - **Android app (v0 target)** is a capture client: local ink preview
     for latency, then stream Ops to the Session host.
3. **One writer:** the Session applies Ops to the Python Document.
   Snapshots and `.apesketch.json` are file formats, not parallel stores.
4. Kotlin (or Capacitor) may power the Android UI. That code is a
   client; TypeScript/Kotlin is not the apeSketch spatial/ink language.

## Alternatives rejected

| Rejected | Why |
|---|---|
| Android owns the canonical board; PC only mirrors | Breaks agent-in-process use next to apeCAD |
| TypeScript core with Python bindings | Splits the toolchain; agents already author Python |
| Dual independent documents with eventual merge | Conflict hell; unnecessary for single-operator desk use |

## Consequences

`SketchSession` on the workstation is the authority. Android joins a
session; it does not redefine persistence. Op schema and Document tests
live in the Python package. Client repos or folders may exist, but
bridges (`to_agent_bundle`, `to_apeCAD`) stay in Python.
