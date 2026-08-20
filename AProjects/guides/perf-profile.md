# Guide — continuous performance monitoring

## Strategy

apeSketch collects board metrics **continuously while the Session host runs**.
The HUD is optional; the recorder is not.

```
board (1 Hz snapshot)
   ├── localStorage ring (~3 min)
   └── POST /api/perf every 5 s → .apeSketch/perf/board-YYYY-MM-DD.jsonl
                                      └── GET /api/perf/summary
```

Use this as features land: denser ink, new tools, Android client. Compare
today’s JSONL (or Export) to an earlier export when something feels slower.

## Enable HUD

- Toolbar **Perf**, or **`P`**, or `?perf=1`
- **Export perf** now includes `live` + `history` + `server_summary`

Monitoring keeps running even with the HUD closed.

## Artifacts

| Location | Contents |
|---|---|
| Browser `localStorage` key `apeSketch.perf.history.v1` | Last ~180 one-second samples |
| `.apeSketch/perf/board-*.jsonl` (gitignored; under the instance root) | Append-only day files for that host |
| `GET /api/perf/summary` | Rolling averages for the current day file |

## Metrics

Same as before (`fps`, `redraw_ms`, `stamp_ms`, `commit_ms`, `emit_ms`,
scene size), plus:

- **trend** lines on the HUD (`vs ~30s`) for redraw/stamp/commit
- **server day** line from `/api/perf/summary`
- Fixed **fps** via a dedicated rAF loop (not “redraws per second”)

## Erase hot path (client)

Partial / stroke erase should stay snappy as scenes grow. Current tactics:

**High**
1. **Overlay canvas** — eraser cursor moves without re-painting ink
2. **AABB culling** — stamp / hit-test skip strokes far from the brush
3. **Path stamping** — interpolate stamps along fast eraser moves
4. **Cached partial runs** — rebuild carved polylines only for touched strokes
5. **Ink bitmap cache** — blit stable strokes; live-draw only open / session ink
6. **Nearby-only partial session** — adopt strokes near the brush, grow as it moves
7. **Batched commit** — one WebSocket `ops` message for the lift

**Medium**
8. **Spatial hash** — cell index for stroke-erase / adopt queries
9. **Point decimation** — drop near-duplicate samples on capture and erase commit
10. **Grid layer cache** — blit cached grid (invalidates on pan/zoom/background)

## Desktop vs tablet feel

Tablets often feel smoother because the canvas is smaller. Desktop lag was
dominated by **rebuilding the full ink/grid bitmaps on every pan pixel** and
uncapped devicePixelRatio. Current mitigations:

- Cap canvas DPR at 1.5
- Pan by **offset-blitting** cached layers; rebuild only on pan end / zoom
- Live stroke on a separate layer (`baseLayer` + `liveLayer`) with coalesced samples
- Continuous FPS rAF only while the Perf HUD is open

```bash
python -m apeSketch --port 9972 --no-browser
node scripts/bench_erase.mjs
node scripts/bench_draw.mjs
# or: npm run bench:draw
```

Draw bench gates (IQ-1 / ADR 0010): `live_stroke` p95 &lt; 4 ms, `input_to_glass` p95 &lt; 25 ms.
Writes `.apeSketch/perf/_bench_draw.json`.

## Workflow while developing

1. Leave the host running during normal use.
2. When a change might affect ink/erase/pan, glance at Perf HUD trends.
3. If something regresses, Export perf and keep the JSON next to the PR/ADR note.
4. Optimize the dominant timer (`stamp_ms` vs `redraw_ms` vs `commit_ms`).

## Out of scope (for now)

- CI perf budgets / automated flamegraphs
- Multi-machine aggregation
- Agent-facing MCP for perf (easy later: read the JSONL)
