from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import select

from app.bot.handlers.voice import handle_voice
from app.core import messages
from app.core.models import VoiceJob, VoiceJobStatus
from app.core.redis import redis


def _voice_message(file_size: int = 20_000, as_audio: bool = False) -> SimpleNamespace:
    ack = SimpleNamespace(message_id=99, edit_text=AsyncMock())
    media = SimpleNamespace(file_id="FILE1", file_size=file_size, duration=4)
    return SimpleNamespace(
        voice=None if as_audio else media,
        audio=media if as_audio else None,
        chat=SimpleNamespace(id=123456789),
        message_id=50,
        answer=AsyncMock(return_value=ack),
        ack=ack,
    )


async def test_voice_acks_then_queues_job(session, user):
    msg = _voice_message()
    await handle_voice(msg, session, user)
    msg.answer.assert_awaited_once_with(messages.VOICE_RECEIVED)

    job = await session.scalar(select(VoiceJob))
    assert job is not None
    assert (job.user_id, job.telegram_file_id, job.chat_id) == (user.id, "FILE1", 123456789)
    assert (job.message_id, job.status_message_id, job.status) == (50, 99, VoiceJobStatus.QUEUED)
    assert await redis.zcard("arq:queue") == 1


async def test_audio_file_is_handled_like_voice(session, user):
    await handle_voice(_voice_message(as_audio=True), session, user)
    assert (await session.scalar(select(VoiceJob))) is not None
    assert await redis.zcard("arq:queue") == 1


async def test_voice_too_long_is_rejected_before_queueing(session, user):
    msg = _voice_message()
    msg.voice.duration = 20 * 60
    await handle_voice(msg, session, user)
    msg.answer.assert_awaited_once_with(
        "❌ Voice note is too long (max 5 minutes). Please send a shorter one."
    )
    assert await session.scalar(select(VoiceJob)) is None


async def test_voice_too_large_is_rejected_before_queueing(session, user):
    msg = _voice_message(file_size=25 * 1024 * 1024)
    await handle_voice(msg, session, user)
    msg.answer.assert_awaited_once_with(
        "❌ Voice note is too big (max 20 MB). Please send a shorter one."
    )
    assert await session.scalar(select(VoiceJob)) is None
    assert await redis.zcard("arq:queue") == 0


async def test_voice_enqueue_failure_updates_ack(session, user, monkeypatch):
    from app.core import queue

    monkeypatch.setattr(
        queue, "enqueue_transcription", AsyncMock(side_effect=OSError("redis down"))
    )
    msg = _voice_message()
    await handle_voice(msg, session, user)
    msg.ack.edit_text.assert_awaited_once_with(messages.SOMETHING_WENT_WRONG)
    job = await session.scalar(select(VoiceJob))
    assert job is not None and job.status == VoiceJobStatus.FAILED  # not orphaned as `queued`


async def test_voice_db_failure_updates_ack_and_leaves_session_usable(session, user, monkeypatch):
    """A failed INSERT must not leak a PendingRollbackError through the error handler."""
    from app.core.models import VoiceJob
    from app.core.services import voice as voice_service

    async def broken_create(session, **kwargs):
        session.add(VoiceJob(**{**kwargs, "user_id": 424242}))  # FK violation: no such user
        await session.commit()

    monkeypatch.setattr(voice_service, "create_voice_job", broken_create)
    msg = _voice_message()
    await handle_voice(msg, session, user)  # must not raise
    msg.ack.edit_text.assert_awaited_once_with(messages.SOMETHING_WENT_WRONG)
    await session.refresh(user)  # raises PendingRollbackError if the handler forgot to roll back
    assert user.id
    assert await redis.zcard("arq:queue") == 0
