"""arq worker: transcription + notification jobs. Run with `arq app.worker.main.WorkerSettings`."""

from pathlib import Path
from typing import Any

from aiogram import Bot
from arq import func
from arq.connections import RedisSettings

from app.core import queue
from app.core.config import get_settings
from app.core.db import engine
from app.core.logging import configure_logging, get_logger
from app.core.redis import redis
from app.worker.jobs.notify import send_notification
from app.worker.jobs.transcribe import transcribe_voice
from app.worker.transcribers import build_transcriber

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger("worker")

READY_FILE = Path("/tmp/worker-ready")  # docker healthcheck: exists once the model is loaded


async def on_startup(ctx: dict[str, Any]) -> None:
    READY_FILE.unlink(missing_ok=True)
    ctx["bot"] = Bot(settings.telegram_bot_token)
    ctx["transcriber"] = build_transcriber(settings)
    await ctx["transcriber"].load()  # fail loudly here, not on the first voice note
    READY_FILE.touch()
    log.info("worker.start", transcriber=settings.transcriber)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    READY_FILE.unlink(missing_ok=True)
    await ctx["bot"].session.close()
    await queue.close_pool()
    await engine.dispose()
    await redis.aclose()
    log.info("worker.stop")


class WorkerSettings:
    functions = [
        func(transcribe_voice, name=queue.TRANSCRIBE_VOICE, timeout=120),
        func(send_notification, name=queue.SEND_NOTIFICATION, timeout=15),
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 5  # upper bound; transcribe_voice enforces its own limit of 3
    max_jobs = 10  # notifications keep flowing while one transcription runs (semaphore in adapter)
    health_check_interval = 30
