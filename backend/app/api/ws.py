"""WebSocket fan-out: one Redis subscription per API process, broadcast to every client."""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import CHANNEL
from app.core.logging import get_logger
from app.core.redis import redis

log = get_logger("ws")
router = APIRouter()


class Broadcaster:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self._listener: asyncio.Task | None = None

    async def start(self) -> None:
        self._listener = asyncio.create_task(self._listen(), name="ws-redis-listener")

    async def stop(self) -> None:
        if self._listener:
            self._listener.cancel()
            try:
                await self._listener
            except asyncio.CancelledError:
                pass

    async def _listen(self) -> None:
        # Reconnect with backoff if the Redis subscription drops; never let the task die quietly.
        delay = 1
        while True:
            try:
                async with redis.pubsub() as pubsub:
                    await pubsub.subscribe(CHANNEL)
                    log.info("ws.subscribed", channel=CHANNEL)
                    delay = 1
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            await self.broadcast(message["data"])
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - keep the listener alive
                log.warning("ws.subscription_lost", error=str(exc), retry_in=delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def broadcast(self, raw: str) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_text(raw)
            except Exception:  # noqa: BLE001 - a dead client must not break the others
                self.clients.discard(ws)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)
        log.info("ws.connected", clients=len(self.clients))

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)
        log.info("ws.disconnected", clients=len(self.clients))


broadcaster = Broadcaster()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await broadcaster.connect(ws)
    try:
        while True:
            await ws.receive_text()  # clients only send pings; content is ignored
    except WebSocketDisconnect:
        broadcaster.disconnect(ws)
