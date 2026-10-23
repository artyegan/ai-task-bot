"""arq job queue access shared by api, bot and worker (enqueue side)."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job

from app.core.config import get_settings

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
