"""Real-time events: published to the Redis `events` channel after a successful commit.

The API process subscribes and fans every message out to WebSocket clients unchanged.
"""

import json
from typing import Any

from app.core.models import Task, utcnow
from app.core.redis import redis
from app.core.schemas import TaskOut, iso_z

CHANNEL = "events"


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
    await redis.publish(CHANNEL, json.dumps(event))
