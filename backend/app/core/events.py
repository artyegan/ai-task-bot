"""Real-time events: published to the Redis `events` channel after a successful commit.

The API process subscribes and fans every message out to WebSocket clients unchanged.
"""

import json
from typing import Any

from app.core.logging import get_logger
from app.core.models import Task, utcnow
from app.core.redis import redis
from app.core.schemas import TaskOut, iso_z

CHANNEL = "events"
log = get_logger("events")


def task_event(event_type: str, task: Task) -> dict[str, Any]:
    return {
        "type": event_type,
        "task": TaskOut.model_validate(task).model_dump(mode="json"),
        "ts": iso_z(utcnow()),
    }


def task_deleted_event(task_id: int) -> dict[str, Any]:
    return {"type": "task.deleted", "task_id": task_id, "ts": iso_z(utcnow())}


def voice_failed_event(voice_job_id: int, user_id: int, error: str) -> dict[str, Any]:
    return {
        "type": "voice.failed",
        "voice_job_id": voice_job_id,
        "user_id": user_id,
        "error": error,
        "ts": iso_z(utcnow()),
    }


async def publish(event: dict[str, Any]) -> None:
    """Best effort: the write is already committed; a dashboard that misses an event refetches
    on reconnect. Never turn a Redis hiccup into a failed request."""
    try:
        await redis.publish(CHANNEL, json.dumps(event))
    except Exception as exc:  # noqa: BLE001
        log.warning("events.publish_failed", type=event.get("type"), error=str(exc))
