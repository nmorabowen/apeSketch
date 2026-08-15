# Guide — Python environment

apeSketch uses the shared OpenSees toolchain venv, not a repo-local `.venv`.

| Item | Path |
|---|---|
| Venv folder | `C:\Users\nmb\venv\opensees_env` |
| Python | `C:\Users\nmb\venv\opensees_env\Scripts\python.exe` |
| Activate (PowerShell) | `C:\Users\nmb\venv\opensees_env\Scripts\Activate.ps1` |

Install / refresh (from the apeSketch checkout):

```powershell
C:\Users\nmb\venv\opensees_env\Scripts\python.exe -m pip install -e ".[dev,host]"
```

Host extras (`websockets`, `segno`) are required for live WS + QR pairing.

```powershell
C:\Users\nmb\venv\opensees_env\Scripts\python.exe -m apeSketch
```
