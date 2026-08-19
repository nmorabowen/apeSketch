# Intent

apeSketch captures **hand ink** and turns it into a durable document for
agents and for the ape* toolchain.

## Is

- An ink **bridge**: tablet / stylus → Session Document → agents / apeCAD
- Document-first (Python), MIT, same spirit as apeCAD
- Dual agent egress: structured strokes + on-demand raster

## Is not

- A full whiteboard SaaS or Excalidraw competitor
- A CAD modeller (that is apeCAD’s spatial intent layer)
- OS-level “phone as Wacom” pointer injection

## Locked ADRs

- [0002](../adrs/0002-ink-bridge-scratchpad.md) — product role
- [0003](../adrs/0003-python-document-clients.md) — Python authority
- [0004](../adrs/0004-lan-session-host.md) — LAN Session host
- [0007](../adrs/0007-instance-scoped-host.md) — one host per instance root
