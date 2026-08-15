"""HTTP + optional WebSocket Session host (prototype P1).

HTTP board works with zero deps. Live multi-client WS needs:
  pip install -e ".[host]"
"""

from __future__ import annotations

import argparse
import asyncio
import json
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
from apeSketch.host.perf_store import append_sample, summarize
from apeSketch.host.qr_svg import board_qr_svg
from apeSketch.session import SketchSession

STATIC_DIR = Path(__file__).resolve().parent / "static"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_HOST = "0.0.0.0"
# Keep clear of apeCAD scratchpad (8765).
DEFAULT_PORT = 9966
ASSET_DIR = REPO_ROOT / ".apeSketch" / "assets"


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class SessionHttpServer(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        session: SketchSession,
        *,
        advertise_host: str,
        ws_port: int,
    ) -> None:
        self.session = session
        self.advertise_host = advertise_host
        self.ws_port = ws_port
        super().__init__(address, SessionHttpHandler)


class SessionHttpHandler(BaseHTTPRequestHandler):
    server: SessionHttpServer  # type: ignore[assignment]

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
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
        if path == "/pair":
            self._send_file(
                STATIC_DIR / "pair.html",
                "text/html; charset=utf-8",
                no_store=True,
            )
            return
        if path == "/api/snapshot":
            self._send_json(200, self.server.session.snapshot_message())
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
            self._send_json(200, summarize(root=REPO_ROOT))
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
                f'attachment; filename="apesketch-{self.server.session.document.revision}.json"',
            )
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.end_headers()
            self.wfile.write(raw)
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
                meta = append_sample(payload, root=REPO_ROOT)
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
        if parsed.path != "/api/op":
            self._send_json(404, {"error": f"unknown path {parsed.path}"})
            return
        try:
            payload = self._read_json_object()
            message = self.server.session.apply_dict(payload)
            self._send_json(200, message)
        except DocumentError as exc:
            self._send_json(400, {"error": str(exc)})

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

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)


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


async def _run_ws(session: SketchSession, host: str, port: int) -> None:
    try:
        from websockets.asyncio.server import serve
    except ImportError as exc:
        raise SystemExit('WebSocket host requires: pip install -e ".[host]"') from exc

    async def handler(websocket: Any) -> None:
        await _ws_handler(websocket, session)

    async with serve(handler, host, port):
        await asyncio.Future()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="apeSketch ink Session host")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--ws-port", type=int, default=None, help="defaults to HTTP port + 1")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--http-only",
        action="store_true",
        help="serve HTTP board without WebSocket (POST /api/op only)",
    )
    args = parser.parse_args(argv)

    session = SketchSession(Document(), assets=AssetStore(ASSET_DIR))
    http_port = args.port
    ws_port = args.ws_port if args.ws_port is not None else http_port + 1
    advertise = _lan_ip()

    http = SessionHttpServer(
        (args.host, http_port),
        session,
        advertise_host=advertise,
        ws_port=ws_port,
    )
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()

    board_url = f"http://{advertise}:{http_port}/"
    print(f"apeSketch board  {board_url}", flush=True)
    print(f"apeSketch pair   http://{advertise}:{http_port}/pair", flush=True)
    print(f"apeSketch room   {session.room_code}", flush=True)

    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{http_port}/")

    if args.http_only:
        print("apeSketch mode   HTTP only (no WS)", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            http.shutdown()
        return

    pair = session.pair_info(host=advertise, port=ws_port)
    print(f"apeSketch ws     {pair['ws']}", flush=True)
    try:
        asyncio.run(_run_ws(session, args.host, ws_port))
    except KeyboardInterrupt:
        pass
    finally:
        http.shutdown()


if __name__ == "__main__":
    main()
