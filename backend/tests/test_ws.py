"""The WebSocket fan-out: one Redis subscription, every client gets every event."""

import asyncio
import json
from unittest.mock import AsyncMock

from app.api.ws import Broadcaster
from app.core import events
from app.core.redis import redis


async def _wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not await predicate():
        assert asyncio.get_running_loop().time() < deadline, "condition not met in time"
        await asyncio.sleep(0.05)


class FakeSocket:
    def __init__(self, error: Exception | None = None) -> None:
        self.send_text = AsyncMock(side_effect=error)


async def test_broadcaster_fans_out_and_drops_dead_clients():
    broadcaster = Broadcaster()
    good = FakeSocket()
    dead = FakeSocket(RuntimeError("socket closed"))
    broadcaster.clients.update({good, dead})

    await broadcaster.start()
    try:

        async def subscribed():
            return (await redis.pubsub_numsub(events.CHANNEL))[0][1] >= 1

        await _wait_for(subscribed)
        await events.publish(events.task_deleted_event(42))

        async def delivered():
            return good.send_text.await_count >= 1

        await _wait_for(delivered)
        frame = json.loads(good.send_text.await_args.args[0])
        assert frame == {"type": "task.deleted", "task_id": 42, "ts": frame["ts"]}
        assert dead not in broadcaster.clients and good in broadcaster.clients
    finally:
        await broadcaster.stop()
