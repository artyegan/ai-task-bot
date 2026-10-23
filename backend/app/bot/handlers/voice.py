"""Voice message -> instant ack -> queued transcription job."""

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages, queue
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.models import User
from app.core.services import voice as voice_service

log = get_logger("bot.voice")
router = Router(name="voice")


@router.message(F.voice | F.audio)
async def handle_voice(message: Message, session: AsyncSession, user: User) -> None:
    voice = message.voice or message.audio  # voice note, or an audio file sent as a document
    assert voice is not None
    settings = get_settings()
    if voice.file_size and voice.file_size > settings.max_voice_bytes:
        max_mb = settings.max_voice_bytes // (1024 * 1024)
        await message.answer(messages.VOICE_TOO_LARGE.format(max_mb=max_mb))
        return
    if voice.duration and voice.duration > settings.max_voice_seconds:
        max_min = settings.max_voice_seconds // 60
        await message.answer(messages.VOICE_TOO_LONG.format(max_min=max_min))
        return

    user_id = user.id  # read before any failure can expire the ORM object

    # Acknowledge first: the user sees feedback before any DB or queue work happens.
    ack = await message.answer(messages.VOICE_RECEIVED)
    job = None
    try:
        job = await voice_service.create_voice_job(
            session,
            user_id=user_id,
            telegram_file_id=voice.file_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
            status_message_id=ack.message_id,
        )
        await queue.enqueue_transcription(job.id)
    except Exception:
        log.exception("voice.enqueue_failed", user_id=user_id, voice_job_id=job and job.id)
        await session.rollback()  # a failed flush leaves the session unusable until rolled back
        if job is not None:  # row exists but no job was queued: don't leave it `queued` forever
            try:
                await voice_service.mark_failed(session, job, voice_service.INTERNAL_ERROR)
            except Exception:  # noqa: BLE001
                log.exception("voice.mark_failed_failed", voice_job_id=job.id)
        await ack.edit_text(messages.SOMETHING_WENT_WRONG)
        return
    log.info("voice.queued", voice_job_id=job.id, user_id=user_id, seconds=voice.duration)


@router.message()
async def unsupported(message: Message) -> None:
    """Stickers, photos, documents…: say what the bot can do instead of staying silent."""
    await message.answer(messages.UNSUPPORTED_MESSAGE)
