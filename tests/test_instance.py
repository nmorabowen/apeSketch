"""Instance-scoped Session host (ADR 0007)."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener, urlopen

import pytest

from apeSketch.assets import AssetStore
from apeSketch.document import Document
from apeSketch.host.instance import (
    InstancePaths,
    clear_stamp,
    live_host,
    resolve_instance,
    same_root,
)
from apeSketch.host.server import SessionHttpServer, _bind_http, _write_live_stamp
from apeSketch.host.session_store import SessionStore
from apeSketch.ops import BeginStroke
from apeSketch.session import SketchSession
from apeSketch.types import StrokeStyle

_OPENER = build_opener(ProxyHandler({}))


@pytest.fixture(autouse=True)
def _clear_instance_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APESKETCH_ROOT", "APESKETCH_SESSION_SKETCHES", "APESKETCH_ASSETS"):
        monkeypatch.delenv(name, raising=False)


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
    http = _bind_http(
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
    _write_live_stamp(paths, http, advertise_host="127.0.0.1")
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
