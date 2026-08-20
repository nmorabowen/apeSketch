"""HTTP + optional WebSocket Session host (prototype P1).

Live multi-client WS needs ``websockets`` (included in ``pip install apeSketch``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from apeSketch.assets import AssetStore
from apeSketch.document import Document
from apeSketch.errors import DocumentError
from apeSketch.host.instance import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HostStamp,
    InstancePaths,
    clear_stamp,
    iter_http_ports,
    iter_ws_ports,
    live_host,
    resolve_instance,
    wait_until_up,
    write_stamp,
)
from apeSketch.host.perf_store import append_sample, summarize
from apeSketch.host.qr_svg import board_qr_svg
from apeSketch.host.session_store import SessionStore
from apeSketch.session import SketchSession
from apeSketch.substrate import export_filename, title_from_open_request

STATIC_DIR = Path(__file__).resolve().parent / "static"
# Workbench may assign these before calling main(); otherwise resolve_instance.
SESSIONS_DIR: Path | None = None
ASSET_DIR: Path | None = None
AUTOSAVE_DELAY_S = 0.8


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class SessionHttpServer(ThreadingHTTPServer):
    # Exclusive bind so a second instance cannot share a port (ADR 0007).
    allow_reuse_address = False
    daemon_threads = True
    block_on_close = False

    def __init__(
        self,
        address: tuple[str, int],
        session: SketchSession,
        *,
        advertise_host: str,
        ws_port: int,
        store: SessionStore,
        instance: InstancePaths,
        http_only: bool = False,
    ) -> None:
        self.session = session
        self.advertise_host = advertise_host
        self.ws_port = ws_port
        self.store = store
        self.instance = instance
        self.http_only = http_only
        self._autosave_timer: threading.Timer | None = None
        self._autosave_lock = threading.Lock()
        super().__init__(address, SessionHttpHandler)
        self.timeout = 0.5
        session.on_change(lambda _msg: self.schedule_autosave())

    def host_payload(self) -> dict[str, Any]:
        return {
            "pid": os.getpid(),
            "root": str(self.instance.root),
            "sessions": str(self.instance.sessions),
            "assets": str(self.instance.assets),
            "http_port": int(self.server_address[1]),
            "ws_port": self.ws_port,
            "advertise_host": self.advertise_host,
            "http_only": self.http_only,
        }

    def session_payload(self) -> dict[str, Any]:
        return {
            "active_id": self.session.session_id,
            "title": self.session.session_title,
            "revision": self.session.document.revision,
            "sessions": [meta.to_dict() for meta in self.store.list()],
        }

    def ensure_bound_session(self) -> dict[str, Any]:
        """Create a library entry if the live board is not bound yet."""
        if self.session.session_id is not None:
            meta = self.store.save(
                self.session.session_id,
                self.session.document,
                title=self.session.session_title,
            )
            self.session.bind_session(meta.id, meta.title)
            return meta.to_dict()
        meta = self.store.create(
            self.session.document,
            title=self.session.session_title,
        )
        self.session.bind_session(meta.id, meta.title)
        return meta.to_dict()

    def schedule_autosave(self) -> None:
        with self._autosave_lock:
            if self._autosave_timer is not None:
                self._autosave_timer.cancel()
            timer = threading.Timer(AUTOSAVE_DELAY_S, self._autosave_now)
            timer.daemon = True
            self._autosave_timer = timer
            timer.start()

    def _autosave_now(self) -> None:
        with self._autosave_lock:
            self._autosave_timer = None
        try:
            if self.session.session_id is None:
                if self.session.document.revision <= 0:
                    return
                self.ensure_bound_session()
                return
            self.store.save(
                self.session.session_id,
                self.session.document,
                title=self.session.session_title,
            )
        except (DocumentError, OSError):
            return

    def flush_autosave(self) -> None:
        with self._autosave_lock:
            if self._autosave_timer is not None:
                self._autosave_timer.cancel()
                self._autosave_timer = None
        try:
            if self.session.session_id is None:
                if self.session.document.revision > 0:
                    self.ensure_bound_session()
                return
            self.store.save(
                self.session.session_id,
                self.session.document,
                title=self.session.session_title,
            )
        except (DocumentError, OSError):
            return


class SessionHttpHandler(BaseHTTPRequestHandler):
    server: SessionHttpServer  # type: ignore[assignment]
    protocol_version = "HTTP/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        self.close_connection = True
        if path in ("/", "/index.html", "/board.html"):
            self._send_file(
                STATIC_DIR / "board.html",
                "text/html; charset=utf-8",
                no_store=True,
            )
            return
        if path == "/board.js":
            self._send_file(
                STATIC_DIR / "board.js",
                "text/javascript; charset=utf-8",
                no_store=True,
            )
            return
        if path == "/selection.js":
            self._send_file(
                STATIC_DIR / "selection.js",
                "text/javascript; charset=utf-8",
                no_store=True,
            )
            return
        if path == "/pair":
            self._send_file(
                STATIC_DIR / "pair.html",
                "text/html; charset=utf-8",
                no_store=True,
            )
            return
        if path == "/api/host":
            self._send_json(200, self.server.host_payload())
            return
        if path == "/api/snapshot":
            self._send_json(200, self.server.session.snapshot_message())
            return
        if path == "/api/sessions":
            self._send_json(200, self.server.session_payload())
            return
        if path == "/api/pair":
            info = self.server.session.pair_info(
                host=self.server.advertise_host,
                port=self.server.ws_port,
            )
            info["board"] = f"http://{self.server.advertise_host}:{self.server.server_address[1]}/"
            info["pair"] = (
                f"http://{self.server.advertise_host}:{self.server.server_address[1]}/pair"
            )
            info["http_port"] = self.server.server_address[1]
            info["ws_port"] = self.server.ws_port
            self._send_json(200, info)
            return
        if path == "/api/perf/summary":
            self._send_json(200, summarize(directory=self.server.instance.perf))
            return
        if path.startswith("/api/asset/"):
            asset_id = path[len("/api/asset/") :].strip("/")
            if not asset_id or "/" in asset_id:
                self._send_json(404, {"error": "missing asset id"})
                return
            item = self.server.session.assets.get(asset_id)
            if item is None:
                self._send_json(404, {"error": "unknown asset"})
                return
            self.send_response(200)
            self.send_header("Content-Type", item.mime)
            self.send_header("Content-Length", str(len(item.data)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self._cors()
            self.end_headers()
            self.wfile.write(item.data)
            return
        if path == "/api/export/svg":
            page = self.server.session.document.page()
            svg = Document._page_to_svg(page, assets=self.server.session.assets)
            raw = svg.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="apesketch-{self.server.session.document.revision}.svg"',
            )
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/api/export/json":
            payload = self.server.session.document.to_dict()
            raw = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{export_filename(product="apeSketch", revision=self.server.session.document.revision)}"',
            )
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.end_headers()
            self.wfile.write(raw)
            return
        if self._try_brand_file(path):
            return
        if path == "/api/pair/qr.svg":
            info = self.server.session.pair_info(
                host=self.server.advertise_host,
                port=self.server.ws_port,
            )
            board = f"http://{self.server.advertise_host}:{self.server.server_address[1]}/"
            try:
                svg = board_qr_svg(board)
            except DocumentError as exc:
                self._send_json(503, {"error": str(exc)})
                return
            raw = svg.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
            return
        self._send_json(404, {"error": f"unknown path {path}"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/perf":
            try:
                payload = self._read_json_object()
                meta = append_sample(payload, directory=self.server.instance.perf)
                self._send_json(200, meta)
            except DocumentError as exc:
                self._send_json(400, {"error": str(exc)})
            except OSError as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if parsed.path in ("/api/asset", "/api/asset/"):
            try:
                payload = self._read_json_object()
                mime = payload.get("mime", "image/png")
                data_b64 = payload.get("data_base64")
                if not isinstance(mime, str) or not isinstance(data_b64, str):
                    raise DocumentError("mime and data_base64 required")
                item = self.server.session.assets.put_base64(data_b64, mime)
                self._send_json(
                    200,
                    {
                        "asset_id": item.asset_id,
                        "mime": item.mime,
                        "bytes": len(item.data),
                        "url": f"/api/asset/{item.asset_id}",
                    },
                )
            except DocumentError as exc:
                self._send_json(400, {"error": str(exc)})
            except OSError as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if parsed.path == "/api/sessions/save":
            try:
                payload = self._read_json_object_optional()
                title = payload.get("title")
                if title is not None and not isinstance(title, str):
                    raise DocumentError("title must be a string")
                if isinstance(title, str) and title.strip():
                    self.server.session.session_title = title.strip()
                meta = self.server.ensure_bound_session()
                self._send_json(200, {"session": meta, **self.server.session_payload()})
            except DocumentError as exc:
                self._send_json(400, {"error": str(exc)})
            except OSError as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if parsed.path == "/api/sessions/new":
            try:
                payload = self._read_json_object_optional()
                title = payload.get("title")
                if title is not None and not isinstance(title, str):
                    raise DocumentError("title must be a string")
                self.server.flush_autosave()
                label = title.strip() if isinstance(title, str) and title.strip() else "Untitled"
                doc = Document()
                meta = self.server.store.create(doc, title=label)
                self.server.session.replace_document(
                    doc,
                    session_id=meta.id,
                    session_title=meta.title,
                )
                self._send_json(
                    200,
                    {
                        "session": meta.to_dict(),
                        "snapshot": self.server.session.snapshot_message(),
                        **self.server.session_payload(),
                    },
                )
            except DocumentError as exc:
                self._send_json(400, {"error": str(exc)})
            except OSError as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if parsed.path == "/api/sessions/load":
            try:
                payload = self._read_json_object()
                sid = payload.get("id")
                if not isinstance(sid, str) or not sid:
                    raise DocumentError("id required")
                self.server.flush_autosave()
                meta, doc = self.server.store.load(sid)
                self.server.session.replace_document(
                    doc,
                    session_id=meta.id,
                    session_title=meta.title,
                )
                self._send_json(
                    200,
                    {
                        "session": meta.to_dict(),
                        "snapshot": self.server.session.snapshot_message(),
                        **self.server.session_payload(),
                    },
                )
            except DocumentError as exc:
                self._send_json(400, {"error": str(exc)})
            except OSError as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if parsed.path == "/api/sessions/open":
            try:
                payload = self._read_json_object()
                doc_raw = payload.get("document")
                if not isinstance(doc_raw, dict):
                    raise DocumentError("document object required")
                title = payload.get("title")
                filename = payload.get("filename")
                if title is not None and not isinstance(title, str):
                    raise DocumentError("title must be a string")
                if filename is not None and not isinstance(filename, str):
                    raise DocumentError("filename must be a string")
                label = title_from_open_request(title, filename)
                self.server.flush_autosave()
                doc = Document.from_dict({str(k): v for k, v in doc_raw.items()})
                meta = self.server.store.create(doc, title=label)
                self.server.session.replace_document(
                    doc,
                    session_id=meta.id,
                    session_title=meta.title,
                )
                self._send_json(
                    200,
                    {
                        "session": meta.to_dict(),
                        "snapshot": self.server.session.snapshot_message(),
                        **self.server.session_payload(),
                    },
                )
            except DocumentError as exc:
                self._send_json(400, {"error": str(exc)})
            except OSError as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if parsed.path == "/api/sessions/rename":
            try:
                payload = self._read_json_object()
                sid = payload.get("id")
                title = payload.get("title")
                if not isinstance(sid, str) or not sid:
                    raise DocumentError("id required")
                if not isinstance(title, str):
                    raise DocumentError("title must be a string")
                meta = self.server.store.rename(sid, title)
                if self.server.session.session_id == sid:
                    self.server.session.bind_session(meta.id, meta.title)
                    self.server.session.broadcast_snapshot()
                self._send_json(200, {"session": meta.to_dict(), **self.server.session_payload()})
            except DocumentError as exc:
                self._send_json(400, {"error": str(exc)})
            except OSError as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if parsed.path == "/api/sessions/delete":
            try:
                payload = self._read_json_object()
                sid = payload.get("id")
                if not isinstance(sid, str) or not sid:
                    raise DocumentError("id required")
                if self.server.session.session_id == sid:
                    raise DocumentError("cannot delete the active session")
                self.server.store.delete(sid)
                self._send_json(200, self.server.session_payload())
            except DocumentError as exc:
                self._send_json(400, {"error": str(exc)})
            except OSError as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if parsed.path != "/api/op":
            self._send_json(404, {"error": f"unknown path {parsed.path}"})
            return
        try:
            payload = self._read_json_object()
            message = self.server.session.apply_dict(payload)
            self._send_json(200, message)
        except DocumentError as exc:
            self._send_json(400, {"error": str(exc)})

    def _read_json_object_optional(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw.strip():
            return {}
        parsed: object = json.loads(raw.decode("utf-8") or "null")
        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise DocumentError("JSON body must be an object")
        return {str(k): v for k, v in parsed.items()}

    def _read_json_object(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        parsed: object = json.loads(raw.decode("utf-8") or "null")
        if not isinstance(parsed, dict):
            raise DocumentError("JSON body must be an object")
        return {str(k): v for k, v in parsed.items()}

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    _BRAND_MIME = {
        ".ico": "image/x-icon",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".css": "text/css",
        ".ttf": "font/ttf",
    }

    def _try_brand_file(self, path: str) -> bool:
        rel: str | None = None
        if path == "/favicon.ico":
            rel = "favicon.ico"
        elif path == "/apple-touch-icon.png":
            rel = "apple-touch-icon.png"
        elif path.startswith("/brand/"):
            rel = path[len("/brand/") :]
        if rel is None or not rel or ".." in Path(rel).parts:
            return False
        candidate = (STATIC_DIR / rel).resolve()
        try:
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return False
        if not candidate.is_file():
            return False
        mime = self._BRAND_MIME.get(candidate.suffix.lower(), "application/octet-stream")
        self._send_file(candidate, mime)
        return True

    def _send_file(self, path: Path, content_type: str, *, no_store: bool = False) -> None:
        if not path.is_file():
            self._send_json(404, {"error": f"missing {path.name}"})
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if no_store:
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()
        self.close_connection = True


async def _ws_handler(websocket: Any, session: SketchSession) -> None:
    request = getattr(websocket, "request", None)
    path = getattr(request, "path", "") if request is not None else ""
    query = parse_qs(urlparse(path).query)
    room = (query.get("room") or [""])[0]
    token = (query.get("token") or [""])[0]
    try:
        session.authorize(room, token)
    except DocumentError:
        await websocket.close(code=4401, reason="unauthorized")
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def on_message(message: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, message)

    session.subscribe(on_message)
    try:
        await websocket.send(json.dumps(session.snapshot_message()))

        async def sender() -> None:
            while True:
                message = await queue.get()
                await websocket.send(json.dumps(message))

        async def receiver() -> None:
            async for raw in websocket:
                try:
                    parsed_msg: object = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"type": "error", "message": "invalid json"}))
                    continue
                if not isinstance(parsed_msg, dict):
                    await websocket.send(
                        json.dumps({"type": "error", "message": "object required"})
                    )
                    continue
                msg_type = parsed_msg.get("type")
                if msg_type == "hello":
                    continue
                if msg_type == "op":
                    op_payload = parsed_msg.get("op")
                    if not isinstance(op_payload, dict):
                        await websocket.send(
                            json.dumps({"type": "error", "message": "op payload required"})
                        )
                        continue
                    try:
                        session.apply_dict(
                            {str(k): v for k, v in op_payload.items()},
                            exclude=on_message,
                        )
                    except DocumentError as exc:
                        await websocket.send(json.dumps({"type": "error", "message": str(exc)}))
                    continue
                if msg_type == "ops":
                    ops_payload = parsed_msg.get("ops")
                    if not isinstance(ops_payload, list) or not ops_payload:
                        await websocket.send(
                            json.dumps({"type": "error", "message": "ops array required"})
                        )
                        continue
                    batch: list[dict[str, Any]] = []
                    for item in ops_payload:
                        if not isinstance(item, dict):
                            await websocket.send(
                                json.dumps({"type": "error", "message": "ops entries must be objects"})
                            )
                            batch = []
                            break
                        batch.append({str(k): v for k, v in item.items()})
                    if not batch:
                        continue
                    try:
                        session.apply_many_dicts(batch, exclude=on_message)
                    except DocumentError as exc:
                        await websocket.send(json.dumps({"type": "error", "message": str(exc)}))
                    continue
                if "op" in parsed_msg:
                    try:
                        session.apply_dict(
                            {str(k): v for k, v in parsed_msg.items()},
                            exclude=on_message,
                        )
                    except DocumentError as exc:
                        await websocket.send(json.dumps({"type": "error", "message": str(exc)}))
                    continue
                await websocket.send(json.dumps({"type": "error", "message": "unknown message"}))

        await asyncio.gather(sender(), receiver())
    finally:
        session.unsubscribe(on_message)


async def _run_ws(
    session: SketchSession,
    host: str,
    port: int,
    *,
    on_bound: Any | None = None,
) -> None:
    try:
        from websockets.asyncio.server import serve
    except ImportError as exc:
        raise SystemExit("WebSocket host requires: pip install apeSketch") from exc

    async def handler(websocket: Any) -> None:
        await _ws_handler(websocket, session)

    last_error: OSError | None = None
    for candidate in iter_ws_ports(port):
        try:
            async with serve(handler, host, candidate) as server:
                sockets = getattr(server, "sockets", None) or []
                bound = int(sockets[0].getsockname()[1]) if sockets else int(candidate)
                if on_bound is not None:
                    on_bound(bound)
                await asyncio.Future()
                return
        except OSError as exc:
            last_error = exc
            continue
    raise OSError(f"no free WebSocket port starting at {port}") from last_error


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


def _bind_http(
    host: str,
    preferred_port: int,
    session: SketchSession,
    *,
    advertise_host: str,
    ws_port: int,
    store: SessionStore,
    instance: InstancePaths,
    http_only: bool,
) -> SessionHttpServer:
    last_error: OSError | None = None
    for port in iter_http_ports(preferred_port):
        try:
            return SessionHttpServer(
                (host, port),
                session,
                advertise_host=advertise_host,
                ws_port=ws_port,
                store=store,
                instance=instance,
                http_only=http_only,
            )
        except OSError as exc:
            last_error = exc
            continue
    raise OSError(
        f"no free HTTP port starting at {preferred_port} — another instance "
        "holds the preferred pair; tried the next ports"
    ) from last_error


def _write_live_stamp(
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

    paths = resolve_instance(
        root=args.root,
        sessions=args.sessions or SESSIONS_DIR,
        assets=args.assets or ASSET_DIR,
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

    http = _bind_http(
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
    _write_live_stamp(paths, http, advertise_host=advertise)
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
        _write_live_stamp(paths, http, advertise_host=advertise)
        pair = session.pair_info(host=advertise, port=bound)
        print(f"apeSketch ws       {pair['ws']}", flush=True)

    try:
        asyncio.run(
            _run_ws(session, args.host, http.ws_port, on_bound=on_ws_bound)
        )
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()


if __name__ == "__main__":
    main()
