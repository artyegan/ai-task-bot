"""transcribe_voice(voice_job_id): download -> transcribe -> create task -> notify.

Retry policy: 3 attempts, backoff 2s / 8s / 30s. Permanent failures (file too large, no
speech, timeout) are not retried. Idempotent: a job that is already done returns at once.

The job owns its timeout (asyncio.timeout -> TimeoutError -> permanent failure). It never
catches CancelledError: that is arq cancelling on worker shutdown, and arq re-queues the job.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from aiogram.exceptions import TelegramAPIError
from arq import Retry

from app.core import messages, queue
from app.core.config import get_settings
from app.core.db import SessionFactory
from app.core.logging import get_logger
from app.core.models import MAX_TITLE_LENGTH, Task, VoiceJob, VoiceJobStatus
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

        text = await _download_and_transcribe(session, job, attempt, bot, transcriber)
        if text is None:
            return None  # failed permanently or re-queued; the user has been told either way
        task = await _complete(session, job, text)
        log.info("voice.done", voice_job_id=job.id, task_id=task.id, chars=len(text))
        await queue.notify_best_effort(
            job.chat_id,
            job.status_message_id,
            messages.VOICE_TASK_CREATED.format(number=task.number, title=task.title),
        )
        return text


async def _download_and_transcribe(
    session: Any, job: VoiceJob, attempt: int, bot: Any, transcriber: Any
) -> str | None:
    """Stage 1. Returns the transcript, or None after a permanent failure (user notified).
    Raises arq's Retry when the attempt should be re-queued."""
    settings = get_settings()
    budget = asyncio.timeout(settings.transcribe_timeout_seconds)
    try:
        async with budget:
            with tempfile.TemporaryDirectory() as tmp:
                audio = Path(tmp) / "voice.oga"
                await _download(bot, job.telegram_file_id, audio, settings.max_voice_bytes)
                return await _transcribe(transcriber, audio)
    except PermanentFailure as exc:
        await _fail(session, job, exc.code)
    except TimeoutError as exc:
        # Builtin TimeoutError is also an OSError raised by socket timeouts: only OUR budget
        # expiring is permanent; a transient network timeout is retried like any OSError.
        if not budget.expired():
            await _retry_or_fail(session, job, attempt, voice_service.DOWNLOAD_FAILED, exc)
        else:
            log.error("voice.timed_out", voice_job_id=job.id, attempt=attempt)
            await _fail(session, job, voice_service.TIMED_OUT)
    except _RETRYABLE as exc:
        code = (
            voice_service.DOWNLOAD_FAILED
            if isinstance(exc, TelegramAPIError | OSError)
            else voice_service.TRANSCRIPTION_FAILED
        )
        await _retry_or_fail(session, job, attempt, code, exc)
    except Exception:  # unknown error: fail loudly, tell the user
        log.exception("voice.internal_error", voice_job_id=job.id)
        await _fail(session, job, voice_service.INTERNAL_ERROR)
        raise
    return None


async def _complete(session: Any, job: VoiceJob, text: str) -> Task:
    """Stage 2. Creates the task and marks the job done in one commit."""
    try:
        return await voice_service.complete_job(session, job, title=text)
    except Exception:
        log.exception("voice.completion_failed", voice_job_id=job.id)
        task = await _recover_after_completion_failure(session, job)
        if task is None:
            raise  # the user has been told; let arq record the failure
        return task  # only the post-commit step failed: the task exists, carry on


async def _recover_after_completion_failure(session: Any, job: VoiceJob) -> Task | None:
    """Never raises. Returns the task if the commit had already gone through; otherwise marks
    the job failed, or, when the database itself is unreachable, at least tells the user."""
    try:
        await session.rollback()
        await session.refresh(job)
        if job.status == VoiceJobStatus.DONE and job.task_id is not None:
            return await session.get(Task, job.task_id)
        await _fail(session, job, voice_service.INTERNAL_ERROR)
    except Exception:
        log.exception("voice.db_unreachable", voice_job_id=job.id)
        await queue.notify_best_effort(
            job.chat_id,
            job.status_message_id,
            messages.VOICE_FAILED.format(
                reason=messages.FAILURE_REASONS[voice_service.INTERNAL_ERROR]
            ),
        )
    return None


_RETRYABLE = (TelegramAPIError, OSError, TranscriptionError)


async def _retry_or_fail(
    session: Any, job: VoiceJob, attempt: int, code: str, exc: BaseException
) -> None:
    """Re-queue with backoff while attempts remain; otherwise fail permanently with `code`."""
    if attempt >= MAX_TRIES:
        log.error("voice.giving_up", voice_job_id=job.id, error=code, detail=str(exc))
        await _fail(session, job, code)
        return
    delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)) - 1]
    log.warning("voice.retry", voice_job_id=job.id, error=code, detail=str(exc), retry_in=delay)
    await voice_service.mark_retry(session, job, code)
    raise Retry(defer=delay) from exc


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
    return text[:MAX_TITLE_LENGTH]


async def _fail(session: Any, job: VoiceJob, code: str) -> None:
    if session.in_transaction():  # a failed flush must be rolled back before reusing the session
        await session.rollback()
        await session.refresh(job)  # rollback expires attributes; reload them explicitly
    await voice_service.mark_failed(session, job, code)
    reason = messages.FAILURE_REASONS.get(code, code)
    text = (
        messages.VOICE_TOO_LARGE.format(max_mb=get_settings().max_voice_bytes // (1024 * 1024))
        if code == voice_service.FILE_TOO_LARGE
        else messages.VOICE_FAILED.format(reason=reason)
    )
    await queue.notify_best_effort(job.chat_id, job.status_message_id, text)
