# ADR 0004 — Workstation hosts the session over LAN WebSocket; Wi-Fi Direct deferred

**Status:** Accepted (2026-08-14)

## Context

We need real-time (or near real-time) ink from an Android tablet into the
active apeSketch Session on the workstation. Options under discussion:

- Pivot through a cloud/office relay server
- Wi-Fi Direct / SoftAP between tablet and PC
- Same-LAN (or hotspot) connection to a host on the PC
- WebRTC DataChannel P2P

We are solving **document Op sync**, not “Android as a virtual Wacom for
arbitrary PC apps” (HID injection). Pairing UX from BooxDraw (short code /
QR into a live room) is a useful **pattern**, not a dependency.

## Decision

**v0 transport:**

1. The **workstation runs the Session host** (HTTP bootstrap + WebSocket
   Op stream), colocated with the Python Document and agent tools.
2. The Android client joins on the **same LAN**, or via phone/PC
   **hotspot** when office Wi-Fi isolates clients.
3. **Pairing:** QR (or short code) carrying `ws://host:port/room/<code>`
   plus a session token. No cloud account required for desk use.
4. Ink preview stays on-device for latency; Ops stream live (point
   stream and/or stroke-complete — detailed in a later Op-schema ADR).
5. Expose a **`Transport` adapter** boundary so a later WebRTC or relay
   backend can replace the LAN WebSocket without rewriting the Document.

**Deferred (not v0):**

- Wi-Fi Direct / SoftAP as the primary path
- Mandatory cloud relay
- WebRTC as the default transport

## Alternatives rejected

| Rejected | Why |
|---|---|
| Wi-Fi Direct first | OEM-fragile APIs, pairing pain, dual-radio issues; little gain vs LAN/hotspot |
| Cloud relay as the only path | Adds ops, latency, and trust for a desk workflow that can stay local |
| WebRTC DataChannel as v0 default | Signaling/ICE complexity; overkill on same LAN |
| Pointer/HID injection into the OS | Wrong problem; strokes must enter our Document for agents/apeCAD |

## Consequences

Real-time on LAN is the expected UX. Firewall prompts on the PC are
acceptable. Cross-network use may later add an optional relay ADR
without changing Op types. Wi-Fi Direct requires a new ADR if revived.
