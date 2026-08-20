# Glossary

| Term | Meaning |
|---|---|
| **Document** | Canonical ink store in Python; source of truth |
| **Op** | Serializable mutation applied to the Document |
| **Session** | Live authority that accepts Ops and serves clients |
| **Instance** | One host process + disk tree (`--root`); not a machine-wide port |
| **Client** | Android or desktop UI that emits Ops; does not own the Document |
| **Stroke** | Ordered points with id, time, pressure, optional tilt |
| **Transport** | How Ops move (v0: LAN WebSocket); swappable behind Session |
| **Agent bundle** | Structured ink + raster (+ bbox index) for model tools |
| **Promote** | Optional mapping of ink into apeCAD entities |
| **Drawing rule** | Per-client capture aid (ruler, guide line) that constrains pointer samples before Ops; not in the Document ([ADR 0009](../adrs/0009-drawing-rules-client-capture.md)) |
