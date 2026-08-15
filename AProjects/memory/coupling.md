# Coupling

```
Android / desktop clients
        │ Ops (LAN WebSocket v0)
        ▼
apeSketch Session + Document
        ├── to_agent_bundle → coding agents / MCP later
        └── to_apeCAD (later) → apeCAD Document → apeSteel / apeGmsh
```

- **apeCAD**: downstream spatial intent; apeSketch stays pre-geometry ink
  until promote is specified.
- **apeSteel / apeGmsh**: do not import apeSketch directly in v0; go
  through apeCAD when geometry exists.
- **External whiteboards**: pattern sources only ([ADR 0005](../adrs/0005-own-core-adopt-patterns.md)).
