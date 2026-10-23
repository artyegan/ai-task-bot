"""transcribe_voice(voice_job_id): download -> transcribe -> create task -> notify.

Retry policy (PLAN 4b): 3 attempts, backoff 2s / 8s / 30s. Permanent failures (file too
large, no speech) are not retried. Idempotent: a job that is already done returns at once.
"""

import tempfile
from pathlib import Path
from typing import Any

from aiogram.exceptions import TelegramAPIError
from arq import Retry

from app.core import messages, queue
from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.logging import get_logger
from app.core.models import TaskSource, VoiceJob, VoiceJobStatus
from app.core.services import tasks as task_service
from app.core.services import voice as voice_service
from app.worker.transcribers.base import TranscriptionError

log = get_logger("worker.transcribe")

MAX_TRIES = 3
BACKOFF_SECONDS = (2, 8, 30)


class PermanentFailure(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def transcribe_voice(ctx: dict[str, Any], voice_job_id: int) -> str | None:
    bot, transcriber = ctx["bot"], ctx["transcriber"]
    attempt = ctx.get("job_try", 1)
    settings = get_settings()

    async with SessionFactory() as session:
        job = await session.get(VoiceJob, voice_job_id)
        if job is None:
            log.warning("voice.job_missing", voice_job_id=voice_job_id)
            return None
        if job.status == VoiceJobStatus.DONE:
            log.info("voice.already_done", voice_job_id=job.id, task_id=job.task_id)
            return None
        await voice_service.mark_processing(session, job)
        log.info("voice.start", voice_job_id=job.id, attempt=attempt)

        try:
            with tempfile.TemporaryDirectory() as tmp:
                audio = Path(tmp) / "voice.oga"
                await _download(bot, job.telegram_file_id, audio, settings.max_voice_bytes)
                text = await _transcribe(transcriber, audio)
        except PermanentFailure as exc:
            await _fail(session, job, exc.code)
            return None
        except _RETRYABLE as exc:
            code = (
                voice_service.DOWNLOAD_FAILED
                if isinstance(exc, TelegramAPIError | OSError)
                else voice_service.TRANSCRIPTION_FAILED
            )
            if attempt >= MAX_TRIES:
                log.error("voice.giving_up", voice_job_id=job.id, error=code, detail=str(exc))
                await _fail(session, job, code)
                return None
            delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)) - 1]
            log.warning(
                "voice.retry", voice_job_id=job.id, error=code, detail=str(exc), retry_in=delay
            )
            await voice_service.mark_retry(session, job, code)
            raise Retry(defer=delay) from exc
        except Exception as exc:  # noqa: BLE001 - unknown error: fail loudly, tell the user
            log.exception("voice.internal_error", voice_job_id=job.id)
            await _fail(session, job, voice_service.INTERNAL_ERROR)
            raise exc

        task = await task_service.create_task(
            session,
            user_id=job.user_id,
            title=text,
            source=TaskSource.VOICE,
            telegram_message_id=job.message_id,
        )
        await voice_service.mark_done(session, job, task.id)
        log.info("voice.done", voice_job_id=job.id, task_id=task.id, chars=len(text))
        await queue.enqueue_notification(
            job.chat_id,
            job.status_message_id,
            messages.VOICE_TASK_CREATED.format(number=task.number, title=task.title),
        )
        return text


_RETRYABLE = (TelegramAPIError, OSError, TranscriptionError)


async def _download(bot: Any, file_id: str, destination: Path, max_bytes: int) -> None:
    file = await bot.get_file(file_id)
    if file.file_size and file.file_size > max_bytes:
        raise PermanentFailure(voice_service.FILE_TOO_LARGE)
    await bot.download_file(file.file_path, destination=destination)
    if not destination.exists() or destination.stat().st_size == 0:
        raise OSError("downloaded file is empty")


async def _transcribe(transcriber: Any, audio: Path) -> str:
    text = (await transcriber.transcribe(audio)).strip()
    if not text:
        raise PermanentFailure(voice_service.TRANSCRIPTION_EMPTY)
    return text[:500]  # title column limit


async def _fail(session: Any, job: VoiceJob, code: str) -> None:
    await voice_service.mark_failed(session, job, code)
    reason = messages.FAILURE_REASONS.get(code, code)
    text = (
        messages.VOICE_TOO_LARGE.format(max_mb=get_settings().max_voice_bytes // (1024 * 1024))
        if code == voice_service.FILE_TOO_LARGE
        else messages.VOICE_FAILED.format(reason=reason)
    )
    await queue.enqueue_notification(job.chat_id, job.status_message_id, text)
