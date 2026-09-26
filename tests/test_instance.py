"""Instance-scoped Session host (ADR 0007)."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener, urlopen

import pytest

from apeSketch.assets import AssetStore
from apeSketch.document import Document
from apeSketch.host.cli import write_live_stamp
from apeSketch.host.instance import (
    InstancePaths,
    clear_stamp,
    live_host,
    pid_alive,
    resolve_instance,
    same_root,
)
from apeSketch.host.server import SessionHttpServer, bind_http
from apeSketch.host.session_store import SessionStore
from apeSketch.ops import BeginStroke
from apeSketch.session import SketchSession
from apeSketch.types import StrokeStyle

_OPENER = build_opener(ProxyHandler({}))


@pytest.fixture(autouse=True)
def _clear_instance_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APESKETCH_ROOT", "APESKETCH_SESSION_SKETCHES", "APESKETCH_ASSETS"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _no_console_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Windows `os.kill(pid, 0)` is CTRL_C_EVENT, not a probe; on Python
    3.11 a failed one falls through to TerminateProcess and can end this very
    test run with no summary. Make such a call fail loudly instead."""
    if sys.platform != "win32":
        return
    real_kill = os.kill

    def _guarded(pid: int, sig: int) -> None:
        if sig in (signal.CTRL_C_EVENT, signal.CTRL_BREAK_EVENT):
            raise AssertionError(f"os.kill({pid}, {sig}) sends a console signal; it is no probe")
        real_kill(pid, sig)

    monkeypatch.setattr(os, "kill", _guarded)


def test_resolve_default_is_cwd(tmp_path: Path) -> None:
    paths = resolve_instance(cwd=tmp_path)
    assert paths.root == (tmp_path / ".apeSketch").resolve()
    assert paths.sessions == paths.root / "sessions"
    assert paths.assets == paths.root / "assets"
    assert paths.perf == paths.root / "perf"
    assert paths.stamp == paths.root / "host.json"


def test_resolve_workbench_layout(tmp_path: Path) -> None:
    tool = tmp_path / "tools" / "apeSketch"
    (tool / "files").mkdir(parents=True)
    (tool / "pictures").mkdir()
    paths = resolve_instance(root=tool, cwd=tmp_path)
    assert paths.root == tool.resolve()
    assert paths.sessions == (tool / "files").resolve()
    assert paths.assets == (tool / "pictures").resolve()


def test_resolve_sessions_env_sets_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    files = tmp_path / "tools" / "apeSketch" / "files"
    pictures = tmp_path / "tools" / "apeSketch" / "pictures"
    files.mkdir(parents=True)
    pictures.mkdir()
    monkeypatch.setenv("APESKETCH_SESSION_SKETCHES", str(files))
    paths = resolve_instance(cwd=tmp_path)
    assert paths.sessions == files.resolve()
    assert paths.root == files.resolve().parent
    assert paths.assets == pictures.resolve()


def _start(root: Path, preferred: int) -> tuple[SessionHttpServer, InstancePaths]:
    paths = resolve_instance(root=root)
    store = SessionStore(paths.sessions)
    session = SketchSession(assets=AssetStore(paths.assets))
    http = bind_http(
        "127.0.0.1",
        preferred,
        session,
        advertise_host="127.0.0.1",
        ws_port=0,
        store=store,
        instance=paths,
        http_only=True,
    )
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    http.serve_thread = thread
    time.sleep(0.05)
    write_live_stamp(paths, http, advertise_host="127.0.0.1")
    return http, paths


def _stop(http: SessionHttpServer, root: Path) -> None:
    http.flush_autosave()
    clear_stamp(root / "host.json")
    http.shutdown()
    thread = getattr(http, "serve_thread", None)
    if isinstance(thread, threading.Thread):
        thread.join(timeout=3)
    http.server_close()


def test_api_host_reports_instance_root(tmp_path: Path) -> None:
    root = tmp_path / "a"
    http, paths = _start(root, 0)
    try:
        with _OPENER.open(f"http://127.0.0.1:{http.server_address[1]}/api/host", timeout=2) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["root"] == str(paths.root)
        assert payload["http_port"] == http.server_address[1]
        assert payload["pid"] == os.getpid()
    finally:
        _stop(http, paths.root)


def test_brand_favicon_is_served(tmp_path: Path) -> None:
    http, paths = _start(tmp_path / "brand", 0)
    try:
        port = http.server_address[1]
        with _OPENER.open(f"http://127.0.0.1:{port}/favicon.ico", timeout=2) as resp:
            assert resp.status == 200
            body = resp.read()
        assert body[:4] == b"\x00\x00\x01\x00" or body[:8] == b"\x89PNG\r\n\x1a\n"
        with _OPENER.open(f"http://127.0.0.1:{port}/brand/logo-mark.png", timeout=2) as resp:
            assert resp.status == 200
            assert resp.read()[:8] == b"\x89PNG\r\n\x1a\n"
    finally:
        _stop(http, paths.root)


def test_second_instance_binds_another_port(tmp_path: Path) -> None:
    http_a, paths_a = _start(tmp_path / "a", 0)
    try:
        port_a = int(http_a.server_address[1])
        http_b, paths_b = _start(tmp_path / "b", port_a)
        try:
            assert int(http_b.server_address[1]) != port_a
        finally:
            _stop(http_b, paths_b.root)
    finally:
        _stop(http_a, paths_a.root)


def test_same_root_compares_resolved_paths(tmp_path: Path) -> None:
    root = tmp_path / "inst"
    root.mkdir()
    assert same_root(root, root / "." / "")
    assert not same_root(tmp_path / "a", tmp_path / "b")


def test_api_sessions_open_imports_document(tmp_path: Path) -> None:
    http, paths = _start(tmp_path / "open", 0)
    try:
        port = int(http.server_address[1])
        doc = Document()
        doc.apply(
            BeginStroke(
                stroke_id="s1",
                author="t",
                style=StrokeStyle(color="#111111", width=2),
            )
        )
        body = json.dumps(
            {"document": doc.to_dict(), "filename": "imported.ape.json"}
        ).encode("utf-8")
        req = Request(
            f"http://127.0.0.1:{port}/api/sessions/open",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["session"]["title"] == "imported"
        assert payload["snapshot"]["document"]["revision"] == 1
        assert len(payload["sessions"]) == 1
    finally:
        _stop(http, paths.root)


def test_live_host_without_stamp_is_absent(tmp_path: Path) -> None:
    paths = resolve_instance(root=tmp_path / "one")
    assert live_host(paths) is None


def test_live_host_attaches_to_a_running_host(tmp_path: Path) -> None:
    """ADR 0007 Decision 3: a second launch on the same root attaches."""
    http, paths = _start(tmp_path / "live", 0)
    try:
        stamp = live_host(paths)
        assert stamp is not None
        assert stamp.pid == os.getpid()
        assert stamp.http_port == int(http.server_address[1])
    finally:
        _stop(http, paths.root)


def _orphan_sleeper(tmp_path: Path) -> int:
    """A process this runner is not the parent of, like a host started from
    another terminal. The intermediate that spawns it exits at once."""
    pidfile = tmp_path / "orphan.pid"
    spawn = (
        "import pathlib, subprocess, sys; "
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "pathlib.Path(sys.argv[1]).write_text(str(p.pid))"
    )
    subprocess.run([sys.executable, "-c", spawn, str(pidfile)], check=True, timeout=30)
    return int(pidfile.read_text())


def test_pid_alive_sees_a_host_started_elsewhere(tmp_path: Path) -> None:
    """ADR 0007 Decision 3 hinges on this. From a console the old
    `os.kill(pid, 0)` read such a process as dead, and on Python 3.11 it
    fell through to TerminateProcess and killed it."""
    pid = _orphan_sleeper(tmp_path)
    try:
        assert pid_alive(pid)
        assert pid_alive(pid), "the first probe must leave the process running"
    finally:
        os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while pid_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not pid_alive(pid)


def test_pid_alive_reads_an_exited_child_as_dead() -> None:
    """While we hold its Popen handle, an exited child's process object can
    still be opened on Windows, so only the exit code tells it is gone."""
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert pid_alive(child.pid)
    finally:
        child.kill()
        child.wait(timeout=10)
    assert not pid_alive(child.pid)


def test_pid_alive_counts_a_process_it_may_not_open_as_alive() -> None:
    # System (Windows) and init (POSIX) exist; being refused access means alive.
    assert pid_alive(4 if sys.platform == "win32" else 1)


def test_pid_alive_refuses_impossible_pids() -> None:
    assert not pid_alive(0)
    assert not pid_alive(-1)
    assert not pid_alive(2**40)
    # Past a DWORD, ctypes would wrap this onto our own pid.
    assert not pid_alive(2**32 + os.getpid())
    assert not pid_alive(0x7FFFFFFC)
