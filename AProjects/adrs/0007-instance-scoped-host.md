# ADR 0007 — Session host is instance-scoped, not machine-global

**Status:** Accepted (2026-08-19)  
**Amends:** [0004](0004-lan-session-host.md) (transport unchanged; identity of the host)

## Context

ADR 0004 put the Session host on the workstation over LAN WebSocket. The
prototype then bound a **preferred** port pair (`9966` / `9967`) and wrote
sessions under the apeSketch checkout. Launchers treated that port as
machine identity: if `9966` was already up, a second board attached to
the existing process instead of starting another host.

That is wrong once more than one work folder (or cwd) is live. Two
Habitats would share one Document and one `files/` tree. The first
process that grabbed `9966` owned every sketch on the machine.

Workbench already instances **itself** (same folder attaches; a second
folder takes the next port). apeSketch must do the same.

## Decision

1. **One host process per instance root.** The root owns sessions,
   assets, perf telemetry, and a live `host.json` stamp (`pid`, ports,
   resolved root).
2. **`9966` / `9967` are a preferred default**, not machine identity.
   If that pair is taken by a *different* instance, bind the next free
   pair (`9968` / `9969`, …). `--port 0` is ephemeral.
3. **Same root attaches.** Starting a host for a root whose stamp still
   answers `GET /api/host` with that root prints the live URL and does
   not start a second process.
4. **CLI / env, not a checkout path.** `--root`, `--sessions`,
   `--assets`, plus `APESKETCH_ROOT` / `APESKETCH_SESSION_SKETCHES` /
   `APESKETCH_ASSETS`. Default root is `cwd/.apeSketch`, not the
   library checkout. A workbench-shaped root (`files/` + `pictures/`)
   uses those folders.

Transport stays ADR 0004 (LAN HTTP + WebSocket). This ADR only changes
**which process and which disk tree** that transport serves.

## Alternatives rejected

| Rejected | Why |
|---|---|
| One process, many Documents keyed by path | Mixing folders in one WS room; stop/crash of any Habitat kills all |
| Keep `9966` exclusive and error | Blocks a second legitimate instance |
| Attach whenever `9966` answers | The bug this ADR removes |
| Always ephemeral ports (`:0`) | First instance should stay easy to bookmark; preferred default is fine |

## Consequences

Launchers (Workbench, Habitat) must key attach/stop off the **instance
root** (stamp + `/api/host`), not off a global port. Closing one
instance must not kill another instance’s host. Pair QR / advertised
URLs use the bound ports, not the preferred defaults.
