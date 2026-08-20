"""Host lifecycle: argument parsing, startup, attach, banner, shutdown.

``python -m apeSketch`` and the ``apeSketch`` console script land here
(via the compatibility re-export in ``apeSketch.host.server``).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import threading
import webbrowser
from pathlib import Path

from apeSketch.assets import AssetStore
from apeSketch.document import Document
from apeSketch.host.instance import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HostStamp,
    InstancePaths,
    clear_stamp,
    live_host,
    resolve_instance,
    wait_until_up,
    write_stamp,
)
from apeSketch.host.server import SessionHttpServer, bind_http
from apeSketch.host.session_store import SessionStore
from apeSketch.host.ws import serve_ws
from apeSketch.session import SketchSession


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _resolve_startup_document(
    store: SessionStore,
    *,
    load: str | None,
    resume: bool,
) -> tuple[Document, str | None, str]:
    """Return (document, session_id, title) for host startup."""
    if load:
        candidate = Path(load)
        if candidate.is_file():
            return Document.load(candidate), None, candidate.stem
        meta, doc = store.load(load)
        return doc, meta.id, meta.title
    if resume:
        latest = store.latest()
        if latest is not None:
            meta, doc = store.load(latest.id)
            return doc, meta.id, meta.title
    return Document(), None, "Untitled"


def write_live_stamp(
    paths: InstancePaths,
    http: SessionHttpServer,
    *,
    advertise_host: str,
) -> None:
    write_stamp(
        paths.stamp,
        HostStamp(
            pid=os.getpid(),
            http_port=int(http.server_address[1]),
            ws_port=int(http.ws_port),
            root=str(paths.root),
            advertise_host=advertise_host,
            http_only=http.http_only,
        ),
    )


def _print_banner(
    session: SketchSession,
    paths: InstancePaths,
    *,
    advertise_host: str,
    http_port: int,
    http_only: bool,
) -> None:
    board_url = f"http://{advertise_host}:{http_port}/"
    print(f"apeSketch board    {board_url}", flush=True)
    print(f"apeSketch instance {paths.root}", flush=True)
    print(f"apeSketch pair     http://{advertise_host}:{http_port}/pair", flush=True)
    print(f"apeSketch room     {session.room_code}", flush=True)
    if session.session_id:
        print(
            f"apeSketch session  {session.session_id} · {session.session_title}",
            flush=True,
        )
    else:
        print(f"apeSketch sessions {paths.sessions}", flush=True)
    if http_only:
        print("apeSketch mode     HTTP only (no WS)", flush=True)


def _attach_existing(stamp: HostStamp, paths: InstancePaths, *, no_browser: bool) -> None:
    print(f"apeSketch attach   http://127.0.0.1:{stamp.http_port}/", flush=True)
    print(f"apeSketch instance {paths.root}", flush=True)
    print(f"apeSketch pid      {stamp.pid}", flush=True)
    if stamp.advertise_host and stamp.advertise_host not in ("127.0.0.1", "0.0.0.0"):
        print(
            f"apeSketch board    http://{stamp.advertise_host}:{stamp.http_port}/",
            flush=True,
        )
    if not no_browser:
        webbrowser.open(f"http://127.0.0.1:{stamp.http_port}/")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="apeSketch ink Session host")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="preferred HTTP port (0 = ephemeral; busy preferred pair uses the next)",
    )
    parser.add_argument("--ws-port", type=int, default=None, help="defaults to HTTP port + 1")
    parser.add_argument("--root", default=None, help="instance directory (sessions/assets/perf)")
    parser.add_argument("--sessions", default=None, help="session library directory")
    parser.add_argument("--assets", default=None, help="asset directory")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--http-only",
        action="store_true",
        help="serve HTTP board without WebSocket (POST /api/op only)",
    )
    parser.add_argument(
        "--load",
        default=None,
        help="open a saved session id or a .apesketch.json path",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="open the most recently updated saved session",
    )
    args = parser.parse_args(argv)

    # Workbench may assign server.SESSIONS_DIR / server.ASSET_DIR before main().
    from apeSketch.host import server as server_mod

    paths = resolve_instance(
        root=args.root,
        sessions=args.sessions or server_mod.SESSIONS_DIR,
        assets=args.assets or server_mod.ASSET_DIR,
    )
    existing = live_host(paths)
    if existing is not None:
        _attach_existing(existing, paths, no_browser=args.no_browser)
        return

    store = SessionStore(paths.sessions)
    document, session_id, session_title = _resolve_startup_document(
        store,
        load=args.load,
        resume=args.resume,
    )
    session = SketchSession(document, assets=AssetStore(paths.assets))
    session.bind_session(session_id, session_title)
    advertise = _lan_ip()
    planned_ws = args.ws_port if args.ws_port is not None else (
        0 if args.port == 0 else args.port + 1
    )

    http = bind_http(
        args.host,
        args.port,
        session,
        advertise_host=advertise,
        ws_port=planned_ws,
        store=store,
        instance=paths,
        http_only=args.http_only,
    )
    http_port = int(http.server_address[1])
    if args.ws_port is None:
        http.ws_port = 0 if args.port == 0 else http_port + 1
    _thread = threading.Thread(target=http.serve_forever, daemon=True)
    _thread.start()
    if not wait_until_up(http_port):
        http.shutdown()
        http.server_close()
        raise OSError(f"apeSketch HTTP host did not answer on port {http_port}")
    write_live_stamp(paths, http, advertise_host=advertise)
    _print_banner(
        session,
        paths,
        advertise_host=advertise,
        http_port=http_port,
        http_only=args.http_only,
    )

    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{http_port}/")

    def shutdown() -> None:
        http.flush_autosave()
        clear_stamp(paths.stamp)
        http.shutdown()
        http.server_close()

    if args.http_only:
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            shutdown()
        return

    def on_ws_bound(bound: int) -> None:
        http.ws_port = bound
        write_live_stamp(paths, http, advertise_host=advertise)
        pair = session.pair_info(host=advertise, port=bound)
        print(f"apeSketch ws       {pair['ws']}", flush=True)

    try:
        asyncio.run(
            serve_ws(session, args.host, http.ws_port, on_bound=on_ws_bound)
        )
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()


if __name__ == "__main__":
    main()
