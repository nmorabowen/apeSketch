"""One Session host per instance root (ADR 0007).

Preferred ports 9966/9967 are a default, not machine identity.
"""

from __future__ import annotations

import json
import os
import socket
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9966
HOST_STAMP_NAME = "host.json"
PORT_SEARCH_SPAN = 80


@dataclass(frozen=True)
class InstancePaths:
    root: Path
    sessions: Path
    assets: Path
    perf: Path
    stamp: Path


@dataclass(frozen=True)
class HostStamp:
    pid: int
    http_port: int
    ws_port: int
    root: str
    advertise_host: str
    http_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "http_port": self.http_port,
            "ws_port": self.ws_port,
            "root": self.root,
            "advertise_host": self.advertise_host,
            "http_only": self.http_only,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HostStamp | None:
        pid = data.get("pid")
        http_port = data.get("http_port")
        ws_port = data.get("ws_port", 0)
        root = data.get("root")
        advertise = data.get("advertise_host", "127.0.0.1")
        http_only = data.get("http_only", False)
        if not isinstance(pid, int) or pid <= 0:
            return None
        if not isinstance(http_port, int) or http_port <= 0:
            return None
        if not isinstance(ws_port, int) or ws_port < 0:
            return None
        if not isinstance(root, str) or not root:
            return None
        if not isinstance(advertise, str) or not advertise:
            advertise = "127.0.0.1"
        if not isinstance(http_only, bool):
            http_only = False
        return cls(
            pid=pid,
            http_port=http_port,
            ws_port=ws_port,
            root=root,
            advertise_host=advertise,
            http_only=http_only,
        )


def _as_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    return Path(raw.strip()).expanduser()


def same_root(left: Path, right: Path) -> bool:
    try:
        a = os.path.normcase(str(left.resolve()))
        b = os.path.normcase(str(right.resolve()))
    except OSError:
        a = os.path.normcase(str(left))
        b = os.path.normcase(str(right))
    return a == b


def resolve_instance(
    *,
    root: str | Path | None = None,
    sessions: str | Path | None = None,
    assets: str | Path | None = None,
    cwd: Path | None = None,
) -> InstancePaths:
    """Map CLI / env / workbench folders onto one instance tree."""
    base = (cwd if cwd is not None else Path.cwd()).resolve()
    root_path = _as_path(root) or _env_path("APESKETCH_ROOT")
    sessions_path = _as_path(sessions) or _env_path("APESKETCH_SESSION_SKETCHES")
    assets_path = _as_path(assets) or _env_path("APESKETCH_ASSETS")

    if root_path is None and sessions_path is not None:
        root_path = sessions_path.expanduser().resolve().parent
    if root_path is None:
        root_path = base / ".apeSketch"
    root_path = root_path.expanduser().resolve()

    workbench_files = root_path / "files"
    workbench_pictures = root_path / "pictures"
    if sessions_path is None and workbench_files.is_dir():
        sessions_path = workbench_files
    if assets_path is None and workbench_pictures.is_dir():
        assets_path = workbench_pictures

    if sessions_path is None:
        sessions_path = root_path / "sessions"
    else:
        sessions_path = sessions_path.expanduser().resolve()
    if assets_path is None:
        assets_path = root_path / "assets"
    else:
        assets_path = assets_path.expanduser().resolve()

    return InstancePaths(
        root=root_path,
        sessions=sessions_path,
        assets=assets_path,
        perf=root_path / "perf",
        stamp=root_path / HOST_STAMP_NAME,
    )


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def read_stamp(path: Path) -> HostStamp | None:
    if not path.is_file():
        return None
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return HostStamp.from_dict({str(k): v for k, v in parsed.items()})


def write_stamp(path: Path, stamp: HostStamp) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stamp.to_dict(), indent=2) + "\n", encoding="utf-8")


def clear_stamp(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        return


_LOCAL_OPENER = build_opener(ProxyHandler({}))


def probe_host(port: int, *, timeout: float = 0.6) -> dict[str, Any] | None:
    url = f"http://127.0.0.1:{port}/api/host"
    try:
        with _LOCAL_OPENER.open(url, timeout=timeout) as response:
            parsed: object = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(k): v for k, v in parsed.items()}


def wait_until_up(port: int, *, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if probe_host(port, timeout=0.25) is not None:
            return True
        time.sleep(0.02)
    return False


def live_host(paths: InstancePaths) -> HostStamp | None:
    """Return the stamp if this instance already has a answering host."""
    stamp = read_stamp(paths.stamp)
    if stamp is None or not pid_alive(stamp.pid):
        return None
    info = probe_host(stamp.http_port)
    if info is None:
        return None
    remote_root = info.get("root")
    if not isinstance(remote_root, str) or not remote_root:
        return None
    if not same_root(Path(remote_root), paths.root):
        return None
    return stamp


def port_in_use(host: str, port: int) -> bool:
    probe_host_name = host if host not in ("", "0.0.0.0") else "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((probe_host_name, port)) == 0


def iter_http_ports(preferred: int, *, span: int = PORT_SEARCH_SPAN) -> Iterator[int]:
    if preferred == 0:
        yield 0
        return
    yield from range(preferred, preferred + span, 2)


def iter_ws_ports(preferred: int, *, span: int = PORT_SEARCH_SPAN) -> Iterator[int]:
    if preferred == 0:
        yield 0
        return
    yield preferred
    for port in range(preferred + 1, preferred + span):
        if port != preferred:
            yield port
