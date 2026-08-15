# Spec — working prototype (P0 → P3)

**Status:** Planned (2026-08-14)  
**ADRs:** 0002, 0003, 0004, 0005

## Goal

A **desk-demoable** loop that proves the locked architecture:

1. Python Document is the authority.
2. A Session host on the workstation accepts Ops over the LAN.
3. At least two clients draw into the same session in near real time.
4. An agent bundle (ink JSON + PNG) can be written from that Document.

This is not product polish. It is the shortest path that cannot be faked
with a single offline canvas.

## Definition of done (prototype)

| # | Criterion |
|---|---|
| 1 | `pip install -e ".[dev]"` and `pytest` pass on Document / Ops |
| 2 | `python -m apeSketch` starts a Session on the LAN (default port **9966**) |
| 3 | PC browser client draws freehand; strokes persist in Python Document |
| 4 | Second client (phone browser on same Wi‑Fi, or second PC tab) joins via QR / short code and strokes appear on the PC session live |
| 5 | Save / load `.apesketch.json` |
| 6 | `document.to_agent_bundle(out_dir)` writes structured ink + PNG |

**Out of scope for this prototype:** apeCAD promote, MCP server, Wi‑Fi Direct, cloud relay, CRDT multi-author merge, native Android APK, tilt, palm rejection polish, accounts.

## Sequencing (do in order)

```
P0 Document + Ops + JSON     (no network)
        ↓
P1 Session host + WS + QR    (LAN)
        ↓
P2 Browser capture clients   (PC + phone browser as tablet stand-in)
        ↓
P3 Agent bundle export       (JSON + PNG)
        ↓
[later] P4 Kotlin Android client (replaces phone browser)
```

Phone **browser** is the tablet stand-in for P2. That validates ADR 0004
without an APK. Native Android is P4 once the Op stream is stable.

---

## P0 — Document + Ops + JSON

**Timebox:** ~1–2 days  
**Depends on:** ADR 0002, 0003, 0005

### Deliverables

| Piece | Notes |
|---|---|
| `src/apeSketch/` package | MIT, Python ≥ 3.11, mirror apeCAD layout |
| Types | `Point(x, y, t, pressure)`, `Stroke(id, points, style?, layer?, author?)`, `Page`, `Document` |
| Ops | `begin_stroke`, `append_points`, `end_stroke`, `erase_stroke`, `clear_page` |
| JSON | `Document.to_dict` / `from_dict` / `to_json` / `from_json` → `.apesketch.json` |
| Tests | Round-trip JSON; apply Op log; erase; clear |

### Op shape (prototype lock)

Stroke-complete batches are simpler but feel laggy. Prototype uses a
**hybrid** that is still one Op language:

```json
{"op": "begin_stroke", "stroke_id": "s1", "author": "tablet", "style": {"color": "#111", "width": 2}}
{"op": "append_points", "stroke_id": "s1", "points": [[x, y, t, p], ...]}
{"op": "end_stroke", "stroke_id": "s1"}
{"op": "erase_stroke", "stroke_id": "s1"}
{"op": "clear_page", "page_id": "p0"}
```

Coordinates: page space, origin top-left, units **CSS pixels** for the
prototype (document a `units` field; mm conversion is later).

### Done when

`pytest` covers create → append → end → serialize → reload → erase.

---

## P1 — Session host (LAN WebSocket)

**Timebox:** ~1–2 days  
**Depends on:** P0, ADR 0004

### Deliverables

| Piece | Notes |
|---|---|
| `SketchSession` | Owns one `Document`; applies Ops; keeps revision counter |
| Host | Bind `0.0.0.0:9966` (not only localhost) so phones can join |
| HTTP | Serve static clients; `GET /api/snapshot`; `GET /api/pair` → `{url, code, ws}` |
| WebSocket | `/ws?room=<code>&token=<tok>` — clients send Ops, receive Ops + snapshots |
| Pairing | Room code + token generated at Session start; QR encodes WS URL |

### Protocol (prototype)

Client → server:

- `{"type": "op", "op": {…}}`
- `{"type": "hello", "author": "pixel-7", "role": "capture"}`

Server → clients:

- `{"type": "op", "rev": N, "op": {…}}` (broadcast, including echo policy TBD)
- `{"type": "snapshot", "rev": N, "document": {…}}` on join
- `{"type": "error", "message": "…"}`

**Authority:** only the server applies Ops to the Document. Clients may
paint local provisional ink; authoritative strokes come from broadcast
or from local apply-after-ack. Prototype may use **server broadcast of
accepted Ops** (simplest).

### Stack choice (prototype)

| Choice | Rationale |
|---|---|
| Prefer **stdlib HTTP** + one small WS helper | Stay close to apeCAD’s zero-friction host |
| Allowed dep: `websockets` (MIT) **or** equivalent | Real-time needs WS; do not invent a WS parser |
| No Node toolchain for the host | Vanilla static JS clients |

If stdlib-only becomes painful, record a one-line dependency ADR; do not
pull FastAPI/Django for P1.

### Done when

Two processes/tabs connect to the same room; an Op from A appears in B’s
WS stream and in `Document.to_dict()` on the server.

---

## P2 — Browser capture clients

**Timebox:** ~2–3 days  
**Depends on:** P1

### Deliverables

| Piece | Notes |
|---|---|
| `static/board.html` + `board.js` | Full-page blackboard; Pointer Events |
| Local ink preview | Draw immediately on pointermove; send `append_points` throttled (~20–30 ms or on animation frame batches) |
| Pressure | `event.pressure` when available; else `0.5` |
| Pairing UI | Show QR + code on host machine; join page accepts code or opens from QR |
| Second client | Phone Chrome/Safari on same Wi‑Fi (or PC hotspot) |

### UX minimum

- Pen / finger draw, undo last stroke (maps to `erase_stroke` of last id), clear
- Status: connected / room code / rev
- No infinite canvas chrome, no shape tools

### Done when

Stylus or finger on phone produces strokes visible on the PC board
within ~100 ms on a quiet LAN, and the Python Document contains those
strokes after `end_stroke`.

---

## P3 — Agent bundle

**Timebox:** ~0.5–1 day  
**Depends on:** P0 (can stub before P2)

### Deliverables

```python
bundle = document.to_agent_bundle(out_dir)
# out_dir/ink.json     — strokes, bounds, rev
# out_dir/board.png    — raster of current page
# out_dir/manifest.json — paths + page size + stroke count
```

PNG via stdlib-friendly path: render simple polylines with **Pillow**
(MIT) as an optional extra `apeSketch[render]`, or SVG-only first and
PNG in a follow-up. Prefer SVG+JSON if Pillow is undesirable for the
first cut; prototype DoD allows SVG instead of PNG if documented.

### Done when

After a drawing session, one Python call yields files an agent can read
without the GUI.

---

## P4 — Native Android (post-prototype)

**Not required to call the prototype “working.”** Replace the phone
browser with a Kotlin app that:

- Captures `MotionEvent` stylus with pressure
- Speaks the same WS Op protocol
- Keeps local preview

Track in a separate spec once P2 is stable.

---

## Repo layout (target)

```
apeSketch/
  README.md
  pyproject.toml
  AProjects/           # already started
  src/apeSketch/
    __init__.py
    __main__.py
    document.py
    ops.py
    session.py
    host/
      server.py        # HTTP + WS
      static/
        board.html
        board.js
        pair.html
  tests/
    test_document.py
    test_ops.py
    test_session.py
```

Mirror apeCAD packaging: editable install, pytest, ruff/pyright when
convenient.

## Port and conflict

| App | Default |
|---|---|
| apeCAD scratchpad | `127.0.0.1:8765` |
| apeSketch Session | `0.0.0.0:9966` (WS `9967`) |

## Risk register

| Risk | Mitigation |
|---|---|
| Office Wi‑Fi blocks client-to-client | Document PC hotspot fallback in pair UI |
| Safari touch / pressure gaps | Mouse/stylus on Android Chrome first |
| WS through firewall | Prompt user to allow Python on private networks |
| Scope creep into Excalidraw UI | Hard out-of-scope list above |

## Suggested calendar

| Day | Focus |
|---|---|
| 1 | P0 Document + Ops + tests + pyproject |
| 2 | P1 Session + WS + snapshot/pair endpoints |
| 3–4 | P2 board.js + phone join demo |
| 5 | P3 agent bundle + README demo script |

## Next action after accepting this spec

Implement **P0** only: package skeleton, `Document` / `Ops`, JSON
round-trip tests. Do not start Android or apeCAD promote until P2 works.
