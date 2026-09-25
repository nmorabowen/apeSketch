# ADR 0012 — Agent surface: `AGENTS.md` + one task guide; no quirk lint yet

**Status:** Proposed (2026-09-25). Merging this branch accepts it.
Revision 1. No adversarial review yet.

## Context

Coding agents do most of the work in this repo: 15 of the 16 non-merge commits
carry an agent co-author trailer (Cursor 12, Claude 3). Yet the repo had no
agent entry point: no `AGENTS.md`, no
`CLAUDE.md`, and `guides/README.md` listed "Agent onboarding" as pending. The
method below comes from a playbook first run on the Ladruno OpenSees fork
(its WP-115). It has three layers, cheapest first, and each layer must be
earned by evidence from this repo:

1. **`AGENTS.md`**, one entry file for every agent (Claude Code reads it
   through a one-line `CLAUDE.md`).
2. **Task guides**, only for the kinds of work that git history shows.
3. **A quirk lint in CI**, only for lessons that have **recurred** (were
   written down and still bit again) and that name a pattern a machine can
   detect.

### Baseline (Phase 0, measured 2026-09-25 on `master` @ `4d3b6e2`)

| Measure | Value |
|---|---|
| Lessons archive | `AProjects/`: 11 ADRs, each with "Alternatives rejected"; 3 guides; 3 memory notes; 2 specs. Plus commit and PR bodies (#1–#11). No gotchas doc, no CHANGELOG. |
| User memory entries about apeSketch | 0 (`~/.claude/projects/*/memory/*.md`, searched for `apesketch`) |
| **Recurrences** (a written lesson that bit again) | **0** |
| Non-merge commits | 16 |
| Commits touching `host/static/board.js` | 9 of 16. It is the highest-churn file: 7,271 lines changed, ahead of `ops.py` at 1,798 |
| Commits adding op kinds | 3 (#2 media, #3 text, #7 selection), each inside a board-feature PR |
| CI | `pages.yml` and `publish.yml` only. **No test or lint job.** |
| `pytest -q` | 74 passed |
| `ruff check src tests` | 0 findings (`ruff check .`: 2 × E501 in `assets/logo/build.py`) |
| `pyright` (strict, `src/`) | 150 errors with pyright 1.1.411. ADR 0011 recorded 146. `src/` has not changed since, so the difference is probably the pyright version (not verified). |

These candidates for "recurrence" were examined and **not** counted:

| Candidate | Why it is not a recurrence |
|---|---|
| Port 8766 collided with apeCAD (#1, 2026-08-14), then 9966 was treated as the host's identity (#4, ADR 0007, 2026-08-19) | The lesson written after #1 was about port assignment ("apeCAD uses 8765"). The lesson from #4 (a port is not an identity) was new. Both have a root cause in common, but no written lesson bit twice. |
| pytest imported a stale editable install (#11, 2026-08-23) | It was found in apeWorkbench #55 and fixed there 7 minutes before #11 merged, in the same session. That is the lesson spreading, not a lesson that bit again after being written down. |
| The host reached into the private `Document._page_to_svg` (ADR 0011) | One incident, fixed in the same PR that wrote the rule. |

**Gate:** zero recurrences means no lint. Git history shows one clear kind of
recurring work, board-client features, so Layer 2 is earned for that work only.

## Decision

1. **`AGENTS.md` at the repo root** is the agent entry point, and `CLAUDE.md`
   is the single line `@AGENTS.md`. `AGENTS.md` is a map: build and test
   commands with their traps, where decisions, specs and guides live,
   cross-repo contracts, and the PR shape. It routes to ADRs and guides and
   does not restate them (AProjects rule 1, "one fact, one home"). It replaces
   the pending "Agent onboarding" row in `guides/README.md`.
   *Accept:* every command in it was run on this branch (Results).
2. **One task guide**, `.claude/skills/apesketch-board-feature/SKILL.md`, for
   the board client and the op vocabulary. It stays under 100 lines. Each
   item names an ADR, spec or guide heading to read and never copies the
   lesson. For the op procedure it routes to `guides/adding-an-op.md` and
   does not duplicate it. The guide's "Verify" section applies a rule from the
   playbook: for a UI, a passing test suite is not sufficient, so you capture
   screenshots and drive real input.
   *Accept:* every heading it cites exists, and the verify procedure was run
   end to end (Results).
3. **`.gitignore`** gains `.claude/*` + `!.claude/skills/`. Before this
   change, a worktree under `.claude/worktrees/` showed up as `?? .claude/`
   in the main checkout.
   *Accept:* `git check-ignore` ignores `.claude/worktrees/*` and
   `.claude/settings.local.json` but not the guide.
4. **`guides/python-env.md`** stops pinning a single user's path
   (`C:\Users\nmb\…`) and gains "Worktrees and editable installs". That
   covers the #11 trap, which also applies to `python -m apeSketch`, not only
   to pytest.
   *Accept:* the `%USERPROFILE%` commands and the import probe were run.
5. **No quirk lint** (see the gate above). Where a lint would start is recorded
   under "Alternatives rejected", in case one is earned later.
6. **Measurement (Phase 6).** After about 10 more PRs, count the review or
   post-merge findings that match an entry already in `AProjects/`. If the
   count does not drop from this baseline, stop investing in guides.

## Alternatives rejected

| Rejected | Why |
|---|---|
| A quirk lint for ADR 0011 growth rule 2 ("host uses only public core API") | A machine can check it. A scratch `ast` survey flags `host/server.py:264` `Document._page_to_svg` on `5be3663` (the parent of the fix) and finds nothing in `host/` on `1687537` (the fix) or on `master`. The one core→host import is the `__main__.py` entry point, which a rule would have to exempt. But there was one incident and zero recurrences, and lints require recurrences. **If it recurs, start from this survey.** |
| A config lint asserting `pythonpath = ["src"]` (#11) | It is a config line, not a code pattern. One incident, and the comment in `pyproject.toml` already sits next to it. |
| Adding a pytest/ruff CI job in this change | That adds a CI gate, not an agent-surface layer, and deserves its own PR. Listed under Open questions. |
| Guides only in `AProjects/guides/` | Claude Code loads `.claude/skills/*` by their descriptions, and `AProjects/guides/` is not loaded that way. The skill file holds pointers only, so the facts still live in `AProjects/`. |
| A separate `apesketch-new-op` skill | It would duplicate `adding-an-op.md`, which breaks "one fact, one home". Op work has always arrived inside a board-feature PR. |
| A separate visual-verification guide | The repo has one UI. A section of the board guide covers it; split it out if it grows. |
| This plan in `docs/` | `docs/` is the public Pages site (`pages.yml` uploads it on every push to `master`). ADR 0001 also rejects `docs/` as the working-memory home. |
| Porting another repo's rules | The method transfers between repos; rules never do. Every rule has to come from this repo's own incidents. |
| A command index for `scripts/` | Two bench scripts, already listed in `package.json` `scripts`. Nothing to discover. |

## Consequences

- Agents start at `AGENTS.md`, and humans start at `AProjects/README.md` as
  before.
- A new trap goes where it belongs: an ADR if it decides something, a guide
  or memory note otherwise. The guide then gains one line pointing to it.
- When a written lesson bites a second time, revisit Layer 3. The first
  candidate is the ADR 0011 rule-2 survey above.

## Results (2026-09-25)

| Check | Result |
|---|---|
| `python -m pytest -q` (venv, worktree) | 74 passed; imports resolved to the worktree's `src/` |
| `python -m ruff check src tests` | All checks passed |
| `python -m pyright` | 150 errors (baseline above; this change adds no Python) |
| Import probe from a worktree, no `PYTHONPATH` | `…\apeSketch\src\apeSketch\__init__.py`, the **main checkout** |
| Same, with `PYTHONPATH=src` | the worktree's `src\apeSketch\__init__.py` |
| `python -m apeSketch --root <scratch> --port 0 --no-browser` | host up; `host.json` has the pid and ports; `GET /api/host` reports the scratch root |
| Board in a browser | loads with no console errors; `__apeSketchBench` and `__apeSketchRules` are present; `runDecimateCheck()` passes |
| Pointer drag on the canvas | stroke drawn; `GET /api/snapshot` has it; a second tab showed a later stroke live |
| Stop by PID (`taskkill /PID … /F`) | host down; `host.json` left behind, as documented |
| Second start on a **live** root | **did not attach**; it started a second host. See the next section |
| Guide and `AGENTS.md` pointers | all 36 cited ADR/spec/guide headings and code names found by a grep script |
| `git check-ignore` | `.claude/worktrees/x` and `.claude/settings.local.json` ignored; the guide is tracked |
| Benches (`scripts/bench_*.mjs`) | **not verified**. Playwright is not installed on this machine |

### Found while verifying (not fixed)

**Same-root attach does not work on Windows.** `host/instance.py:151`
`pid_alive()` calls `os.kill(pid, 0)`. On Windows `signal.CTRL_C_EVENT == 0`,
so CPython sends it to `GenerateConsoleCtrlEvent`. For an ordinary PID that
call raises `OSError` (WinError 87), and `pid_alive` returns `False` for a
live host. So `live_host()` (`instance.py:213`) never returns a stamp,
`cli.main` never attaches, and a second start on the same root starts a second
host and overwrites `host.json`. That breaks ADR 0007 Decision 3 on the
platform this repo is developed on.

Reproduced here: host A (pid 20108) was answering `GET /api/host` for the root
while `pid_alive(20108)` returned `False`, and the second start printed a new
board URL instead of `apeSketch attach`. No test covers attaching to a live
foreign PID (`tests/test_instance.py` tests only the missing-stamp case). What
two hosts do when both autosave into one sessions directory: **not verified**.

This is production code, so it is left for its own PR after review. Nothing
here depends on it, and there is no merge-order constraint.

## Open questions

- Should CI run `pytest` and `ruff check src tests`? Today nothing enforces
  ADR 0011 growth rule 6.
- The README's "From this checkout" block still pins `C:\Users\nmb\…`. It is
  the PyPI long description, so it was left alone here.
- ADR 0011 was merged, which accepted it, but the index still lists it as
  "Proposed".
