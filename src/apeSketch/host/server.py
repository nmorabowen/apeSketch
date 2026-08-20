"""HTTP Session host: routes, static files, autosave.

The WebSocket bridge lives in ``apeSketch.host.ws``; the CLI and host
lifecycle live in ``apeSketch.host.cli``. ``main`` is re-exported here
for the ``apeSketch`` console script and older callers.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from apeSketch.document import Document
from apeSketch.errors import DocumentError
from apeSketch.export import page_to_svg
from apeSketch.host.instance import InstancePaths, iter_http_ports
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
            svg = page_to_svg(page, assets=self.server.session.assets)
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
            download_name = export_filename(
                product="apeSketch", revision=self.server.session.document.revision
            )
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{download_name}"',
            )
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/api/pair/qr.svg":
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
        if not path.startswith("/api/") and self._try_static_file(path):
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

    _STATIC_MIME = {
        ".ico": "image/x-icon",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".css": "text/css",
        ".ttf": "font/ttf",
        ".woff2": "font/woff2",
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".html": "text/html; charset=utf-8",
    }
    # Client code should always be fresh during development; assets may cache.
    _STATIC_NO_STORE = {".js", ".mjs", ".css", ".html"}

    def _try_static_file(self, path: str) -> bool:
        """Serve any whitelisted file under static/ (client modules, brand, fonts)."""
        if path == "/favicon.ico":
            rel = "favicon.ico"
        elif path == "/apple-touch-icon.png":
            rel = "apple-touch-icon.png"
        elif path.startswith("/brand/"):
            rel = path[len("/brand/") :]
        else:
            rel = path.lstrip("/")
        if not rel or ".." in Path(rel).parts:
            return False
        suffix = Path(rel).suffix.lower()
        mime = self._STATIC_MIME.get(suffix)
        if mime is None:
            return False
        candidate = (STATIC_DIR / rel).resolve()
        try:
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return False
        if not candidate.is_file():
            return False
        self._send_file(candidate, mime, no_store=suffix in self._STATIC_NO_STORE)
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


def bind_http(
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


def main(argv: list[str] | None = None) -> None:
    """Console-script entry point; the implementation lives in host.cli."""
    from apeSketch.host.cli import main as cli_main

    cli_main(argv)


if __name__ == "__main__":
    main()
