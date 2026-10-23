"""Voice job state machine: queued -> processing -> done | failed."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events
from app.core.models import Task, TaskSource, VoiceJob, VoiceJobStatus, utcnow
from app.core.services import tasks as task_service

# Failure codes stored in voice_jobs.error and sent in the voice.failed event.
FILE_TOO_LARGE = "file_too_large"
DOWNLOAD_FAILED = "download_failed"
TRANSCRIPTION_FAILED = "transcription_failed"
TRANSCRIPTION_EMPTY = "transcription_empty"
INTERNAL_ERROR = "internal_error"
TIMED_OUT = "timed_out"


async def create_voice_job(
    session: AsyncSession,
    *,
    user_id: int,
    telegram_file_id: str,
    chat_id: int,
    message_id: int,
    status_message_id: int | None,
) -> VoiceJob:
    job = VoiceJob(
        user_id=user_id,
        telegram_file_id=telegram_file_id,
        chat_id=chat_id,
        message_id=message_id,
        status_message_id=status_message_id,
    )
    session.add(job)
    await session.commit()
    return job


async def mark_processing(session: AsyncSession, job: VoiceJob) -> None:
    job.status = VoiceJobStatus.PROCESSING
    job.attempts += 1
    job.updated_at = utcnow()
    await session.commit()


async def complete_job(session: AsyncSession, job: VoiceJob, *, title: str) -> Task:
    """Create the task AND mark the job done in one transaction, so a retry after a crash
    can never find a created task next to a job that still says `processing`."""
    task = await task_service.stage_task(
        session,
        user_id=job.user_id,
        title=title,
        source=TaskSource.VOICE,
        telegram_message_id=job.message_id,
    )
    job.status = VoiceJobStatus.DONE
    job.task_id = task.id
    job.error = None
    job.updated_at = utcnow()
    await session.commit()
    await task_service.publish_created(session, task)
    return task


async def mark_retry(session: AsyncSession, job: VoiceJob, error: str) -> None:
    """Attempt failed but will be retried: back to queued, remember why."""
    job.status = VoiceJobStatus.QUEUED
    job.error = error
    job.updated_at = utcnow()
    await session.commit()


async def mark_failed(session: AsyncSession, job: VoiceJob, error: str) -> None:
    job.status = VoiceJobStatus.FAILED
    job.error = error
    job.updated_at = utcnow()
    await session.commit()
    await events.publish(events.voice_failed_event(job.id, job.user_id, error))
