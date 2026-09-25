# Guide — Python environment

apeSketch uses the shared OpenSees toolchain venv, not a repo-local `.venv`.
The venv lives under each user's profile (`%USERPROFILE%`). On one workstation
that is `C:\Users\nmb\...`, on another `C:\Users\nmora\...`.

| Item | Path |
|---|---|
| Venv folder | `%USERPROFILE%\venv\opensees_env` |
| Python | `%USERPROFILE%\venv\opensees_env\Scripts\python.exe` |
| Activate (PowerShell) | `& "$env:USERPROFILE\venv\opensees_env\Scripts\Activate.ps1"` |

Released package:

```powershell
& "$env:USERPROFILE\venv\opensees_env\Scripts\python.exe" -m pip install apeSketch
```

Editable checkout (contributors):

```powershell
& "$env:USERPROFILE\venv\opensees_env\Scripts\python.exe" -m pip install -e ".[dev]"
```

`websockets` and `segno` are base dependencies (live WS + QR pairing).

```powershell
& "$env:USERPROFILE\venv\opensees_env\Scripts\python.exe" -m apeSketch
```

## Worktrees and editable installs

The shared venv holds **one** editable install of apeSketch, pointing at the
main checkout. Anything else that imports `apeSketch`, whether a worktree, a
Cursor or Claude Code session, or a script, gets *that* tree, not the one you
are editing.

- `pytest` is safe: `pythonpath = ["src"]` in `pyproject.toml` puts the local
  `src/` first (PR #11). Before that fix, the suite passed while it was testing
  a stale Cursor worktree.
- Everything else is not: `python -m apeSketch`, ad-hoc scripts, and a REPL.
  From a worktree, set `$env:PYTHONPATH = "src"` first. Check with
  `python -c "import apeSketch; print(apeSketch.__file__)"`.
- Never run `pip install -e .` from a worktree. It re-points the shared venv
  for every other session on the machine, which is how the PR #11 incident
  started.
