"""arq job queue access shared by api, bot and worker (enqueue side)."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("queue")

TRANSCRIBE_VOICE = "transcribe_voice"
SEND_NOTIFICATION = "send_notification"

_pool: ArqRedis | None = None


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue_transcription(voice_job_id: int) -> Job | None:
    return await (await get_pool()).enqueue_job(TRANSCRIBE_VOICE, voice_job_id)


async def enqueue_notification(chat_id: int, message_id: int | None, text: str) -> Job | None:
    return await (await get_pool()).enqueue_job(SEND_NOTIFICATION, chat_id, message_id, text)


async def notify_best_effort(chat_id: int, message_id: int | None, text: str) -> bool:
    """For callers whose own work is already done: log a queue failure instead of raising."""
    try:
        await enqueue_notification(chat_id, message_id, text)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("queue.enqueue_failed", job=SEND_NOTIFICATION, chat_id=chat_id, error=str(exc))
        return False
