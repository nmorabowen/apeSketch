"""WebSocket bridge: LAN clients speak Ops to the SketchSession (ADR 0004).

Only the protocol lives here — session authority stays in
:class:`apeSketch.session.SketchSession`.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlparse

from apeSketch.errors import DocumentError
from apeSketch.host.instance import iter_ws_ports
from apeSketch.session import SketchSession


async def handle_client(websocket: Any, session: SketchSession) -> None:
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
                            message = {"type": "error", "message": "ops entries must be objects"}
                            await websocket.send(json.dumps(message))
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


async def serve_ws(
    session: SketchSession,
    host: str,
    port: int,
    *,
    on_bound: Callable[[int], None] | None = None,
) -> None:
    try:
        from websockets.asyncio.server import serve
    except ImportError as exc:
        raise SystemExit("WebSocket host requires: pip install apeSketch") from exc

    async def handler(websocket: Any) -> None:
        await handle_client(websocket, session)

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
