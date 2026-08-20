# ADR 0008 — Consolidated `.ape.json` document substrate

**Status:** Accepted (2026-08-19)

## Context

apeSketch and apeCAD already share the same document pattern: a Python
ops log is the sole writer; JSON is serialization for save/load and for
agents. Today each tool picks its own filename habit (`.apesketch.json`
vs plain `.json`), even though the on-disk shape is the same family:

```json
{
  "schema": "<product>.document.v<N>",
  "units": "<unit_id>",
  "revision": 0,
  "ops": [ … ]
}
```

We expect more ape* scratchpads and bridges to follow this pattern. A
single family extension keeps Workbench routing, file dialogs, and later
shared I/O obvious. Product-specific semantics stay in the `schema`
field — ink vs spatial CAD remain separate documents (ADR 0002).

## Decision

1. **Family extension:** `.ape.json` is the canonical on-disk suffix for
   all ape* document files in this substrate family.
2. **Routing:** the top-level `schema` string selects the handler
   (`apeSketch.document.v0`, `apeCAD.document.v0`, …). Do not infer
   product from filename alone.
3. **Shared envelope (minimum):** `schema`, `units`, `revision`, and
   either `ops` or a product-defined snapshot block. Products may add
   fields (e.g. apeSketch `pages`) but must not drop the envelope.
4. **Legacy:** `.apesketch.json` remains readable; new writes use
   `.ape.json`. Internal session folders migrate on the next save.
5. **Extraction path:** apeSketch carries a small `substrate` module
   (constants + filename/schema helpers) shaped so it can move into a
   shared `apeDocument` (or similar) package when two or more products
   need it — no shared package is required yet.

## Alternatives rejected

| Rejected | Why |
|---|---|
| Keep per-product extensions only (`.apesketch.json`, `.apecad.json`) | Same JSON family; doubles conventions without adding type safety |
| One merged ape* Document type | Confuses pre-geometry ink with typed spatial intent (ADR 0002) |
| Extract a shared Python package now | Only one repo consumes the helpers today; premature coupling |
| Binary container in v0 | JSON stays diff-friendly; compression can come later |

## Consequences

- apeSketch exports, session documents, and open dialogs prefer
  `.ape.json`.
- apeCAD should adopt the same extension and envelope contract when its
  save/open UI is next touched.
- Cross-product open (e.g. apeWorkbench routing by `schema`) can be
  added without renaming files again.
- ADR 0002 and 0005 references to `.apesketch.json` as *canonical* are
  amended: `.ape.json` is canonical; `.apesketch.json` is legacy.
