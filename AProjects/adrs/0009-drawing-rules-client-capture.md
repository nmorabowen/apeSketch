# ADR 0009 — Drawing rules are per-client capture aids, not Document state

**Status:** Accepted (2026-08-19)

## Context

Structural sketching often needs short straight segments — member axes,
grid-like framing, dimension ticks — without turning apeSketch into a
shape-tool whiteboard ([ADR 0002](0002-ink-bridge-scratchpad.md)). Apps
such as Windows Surface Stylus and Procreate solve this with **rules**:
a draggable straight edge or guide line that constrains ink while the pen
is down, then disappears from the saved artwork.

apeSketch already keeps **viewport pan/zoom** out of the Document
([ADR 0006](0006-viewport-client-camera.md)). Drawing rules belong in the
same layer: they affect how pointer samples become stroke points, not
what the Session persists beyond ink geometry.

## Decision

- **Drawing rules are client-only capture chrome.** Ruler/guide pose,
  rotation, and enable flag live in the board client (and later in native
  clients). They are **not** Ops, not in `.ape.json`, and not broadcast
  over the Session WebSocket.
- **Per client.** Each device may place and rotate its own rule. One
  tablet's ruler does not move another client's ruler. Strokes still
  sync through the normal Op stream once constrained points are emitted.
- **Pure capture.** The Document stores only the resulting polylines
  (`begin_stroke` / `append_points` / `end_stroke`). No guide metadata,
  rule ids, or snap provenance fields on strokes.
- **Constraint at pointer → world → Op.** Before Ops are sent, the client
  maps screen pointer samples to world coordinates, then applies an
  optional rule constraint (project onto the active edge or guide line
  within a tolerance). The server and other clients see ordinary ink.
- **No grid integration.** Rule snap is independent of the ADR 0006
  background grid. The grid remains a visual navigation aid only; rules
  do not snap to grid lines or grid intersections.
- **Not shape tools.** Rules straighten **incoming** samples during an
  active stroke. They do not add rectangles, polylines-as-objects, or
  post-hoc straighten/reshape of finished strokes in v1.

### v1 rule kinds (client implementation scope)

| Kind | Behaviour |
|---|---|
| **Ruler** | Finite straight edge: draggable, rotatable overlay; pen snaps to the nearest point on the edge when within tolerance |
| **Guide line** | Infinite line through two world points (or point + angle); pen snaps to the line when within tolerance |

Optional **angle snap** (0° / 45° / 90° relative to the active rule or
page axes) is a client preference, still not Document state.

## Alternatives rejected

| Rejected | Why |
|---|---|
| Rules as Document objects / Ops | Pollutes ink store; agents do not need ruler chrome; fights multi-client independence |
| Shared rule pose over WebSocket | Couples devices; architect at desk and tablet in field want different aids |
| Persist rules in `.ape.json` | Rules are capture-time UI, not part of the agent bundle or promote path |
| Snap to ADR 0006 grid | Explicit product choice: grid stays visual-only; avoids double-snap ambiguity |
| Server-side constraint | Wrong layer; server has no pointer stream; would require new Op types |
| Shape-tool parity (rect, line objects) | Out of scope per ink-bridge role; rules constrain freehand, not CAD primitives |

## Consequences

- **Python Document / Ops unchanged** for rules. No schema migration.
- **board.js** (and P4 native clients) gain a rule overlay renderer, a
  per-client rule state object, and a `constrainPoint(world, rule)` hook
  on the pointer pipeline before `begin_stroke` / `append_points`.
- **Agent bundle** exports constrained polylines as today; vision and
  structured ink see straight segments without guide metadata.
- **Multi-client sessions** remain valid: each author may draw with or
  without a local rule; synced strokes reflect each author's constrained
  input only.
- **Testing:** rule logic is unit-testable in JS (projection, tolerance,
  angle snap). Python tests unchanged unless we later add optional
  post-export line detection (not implied by this ADR).
- **Later amendments** (new ADR, not edits here): shared optional
  "follow my rule" broadcast, perspective/isometric guides, or Document
  persistence if a workflow proves it necessary.
