"""Worker jobs with a stubbed Telegram Bot and the fake transcriber; DB and Redis are real."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from arq import Retry

from app.core import queue
from app.core.models import TaskSource, VoiceJob, VoiceJobStatus
from app.core.services import tasks as task_service
from app.core.services import voice as voice_service
from app.worker.jobs.notify import send_notification
from app.worker.jobs.transcribe import transcribe_voice
from app.worker.transcribers.fake import FakeTranscriber


class StubBot:
    def __init__(self, file_size: int = 4096, download_error: Exception | None = None):
        self.file_size = file_size
        self.download_error = download_error
        self.sent: list[tuple[int, str]] = []
        self.edited: list[tuple[int, int, str]] = []
        self.edit_error: Exception | None = None

    async def get_file(self, file_id: str):
        return SimpleNamespace(file_path=f"voice/{file_id}.oga", file_size=self.file_size)

    async def download_file(self, file_path: str, destination: Path):
        if self.download_error:
            raise self.download_error
        Path(destination).write_bytes(b"OggS fake audio")

    async def edit_message_text(self, text: str, chat_id: int, message_id: int):
        if self.edit_error:
            raise self.edit_error
        self.edited.append((chat_id, message_id, text))

    async def send_message(self, chat_id: int, text: str):
        self.sent.append((chat_id, text))


@pytest.fixture
def notify(monkeypatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(queue, "enqueue_notification", mock)
    return mock


@pytest.fixture
async def voice_job(session, user):
    return await voice_service.create_voice_job(
        session,
        user_id=user.id,
        telegram_file_id="FILE1",
        chat_id=123456789,
        message_id=50,
        status_message_id=51,
    )


def _ctx(bot, transcriber, job_try: int = 1) -> dict:
    return {"bot": bot, "transcriber": transcriber, "job_try": job_try}


async def test_happy_path_creates_task_and_notifies(session, user, voice_job, notify, event_stream):
    transcriber = FakeTranscriber("  Call the dentist tomorrow ")
    result = await transcribe_voice(_ctx(StubBot(), transcriber), voice_job.id)
    assert result == "Call the dentist tomorrow"
    assert transcriber.calls and transcriber.calls[0].name == "voice.oga"

    items, total = await task_service.list_tasks(session)
    assert total == 1
    task = items[0]
    assert (task.number, task.source, task.telegram_message_id) == (1, TaskSource.VOICE, 50)
    assert task.title == "Call the dentist tomorrow"

    await session.refresh(voice_job)
    assert voice_job.status == VoiceJobStatus.DONE
    assert voice_job.task_id == task.id and voice_job.attempts == 1 and voice_job.error is None

    notify.assert_awaited_once_with(
        123456789, 51, "✅ Task #1 created from voice: Call the dentist tomorrow"
    )
    assert (await event_stream.next())["type"] == "task.created"


async def test_timeout_marks_job_failed_and_notifies(
    session, voice_job, notify, event_stream, monkeypatch
):
    import asyncio

    from app.core.config import get_settings

    class Hanging(FakeTranscriber):
        async def transcribe(self, audio_path):
            await asyncio.sleep(5)
            return "never"

    monkeypatch.setattr(get_settings(), "transcribe_timeout_seconds", 0.2)
    assert await transcribe_voice(_ctx(StubBot(), Hanging()), voice_job.id) is None  # no raise
    await session.refresh(voice_job)
    assert (voice_job.status, voice_job.error) == (VoiceJobStatus.FAILED, "timed_out")
    assert "took too long" in notify.await_args.args[2]
    assert (await event_stream.next())["error"] == "timed_out"
    _, total = await task_service.list_tasks(session)
    assert total == 0


async def test_worker_shutdown_cancellation_is_left_to_arq(session, voice_job, notify):
    """arq cancels running jobs on shutdown and re-queues them: not a failure, not a timeout."""
    import asyncio

    class Interrupted(FakeTranscriber):
        async def transcribe(self, audio_path):
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await transcribe_voice(_ctx(StubBot(), Interrupted()), voice_job.id)
    await session.refresh(voice_job)
    assert voice_job.status == VoiceJobStatus.PROCESSING  # untouched, arq will run it again
    notify.assert_not_awaited()
    # the re-run completes normally
    await transcribe_voice(_ctx(StubBot(), FakeTranscriber("after restart")), voice_job.id)
    await session.refresh(voice_job)
    assert voice_job.status == VoiceJobStatus.DONE and voice_job.attempts == 2


async def test_task_and_job_completion_are_atomic(session, voice_job, notify, monkeypatch):
    """If the single commit in complete_job fails, neither the task nor `done` persists."""
    from sqlalchemy.ext.asyncio import AsyncSession

    original_commit = AsyncSession.commit

    async def commit_fails_when_completing(self):
        if any(
            isinstance(o, VoiceJob) and o.status == VoiceJobStatus.DONE
            for o in list(self.new) + list(self.dirty)
        ):
            raise RuntimeError("commit failed")
        return await original_commit(self)

    monkeypatch.setattr(AsyncSession, "commit", commit_fails_when_completing)
    with pytest.raises(RuntimeError):
        await transcribe_voice(_ctx(StubBot(), FakeTranscriber("atomic")), voice_job.id)
    _, total = await task_service.list_tasks(session)
    assert total == 0  # the staged task was rolled back with the failed commit
    await session.refresh(voice_job)
    assert (voice_job.status, voice_job.task_id, voice_job.error) == (
        VoiceJobStatus.FAILED,
        None,
        "internal_error",
    )
    assert "internal error" in notify.await_args.args[2]


async def test_database_unreachable_after_transcription_still_tells_the_user(
    session, voice_job, notify, monkeypatch
):
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.services import voice as voice_service

    async def db_gone(*_a, **_k):
        raise ConnectionError("database unreachable")

    monkeypatch.setattr(voice_service, "complete_job", db_gone)
    monkeypatch.setattr(AsyncSession, "rollback", db_gone)  # the probe cannot reach the DB either
    with pytest.raises(ConnectionError, match="unreachable"):
        await transcribe_voice(_ctx(StubBot(), FakeTranscriber("lost")), voice_job.id)
    notify.assert_awaited_once()
    assert "internal error" in notify.await_args.args[2]


async def test_transient_socket_timeout_is_retried_not_permanent(session, voice_job, notify):
    bot = StubBot(download_error=TimeoutError("socket timed out"))  # an OSError, not our budget
    with pytest.raises(Retry):
        await transcribe_voice(_ctx(bot, FakeTranscriber("x")), voice_job.id)
    await session.refresh(voice_job)
    assert (voice_job.status, voice_job.error) == (VoiceJobStatus.QUEUED, "download_failed")


async def test_failure_after_commit_still_notifies_and_retry_is_idempotent(
    session, user, voice_job, notify, monkeypatch
):
    from app.core.services import voice as voice_service

    original = voice_service.complete_job

    async def complete_then_crash(sess, job, *, title):
        await original(sess, job, title=title)
        raise RuntimeError("crash after commit")  # commit already happened atomically

    monkeypatch.setattr(voice_service, "complete_job", complete_then_crash)
    assert await transcribe_voice(_ctx(StubBot(), FakeTranscriber("once")), voice_job.id)
    monkeypatch.undo()
    await session.refresh(voice_job)
    assert voice_job.status == VoiceJobStatus.DONE and voice_job.task_id is not None
    notify.assert_awaited_once()
    assert "created from voice: once" in notify.await_args.args[2]
    # a retry creates nothing new
    await transcribe_voice(_ctx(StubBot(), FakeTranscriber("twice")), voice_job.id)
    _, total = await task_service.list_tasks(session)
    assert total == 1


async def test_notification_queue_failure_after_completion_is_logged_not_raised(
    session, user, voice_job, monkeypatch
):
    async def broken(*_a, **_k):
        raise ConnectionError("redis down")

    monkeypatch.setattr(queue, "enqueue_notification", broken)
    assert await transcribe_voice(_ctx(StubBot(), FakeTranscriber("kept")), voice_job.id) == "kept"
    await session.refresh(voice_job)
    assert voice_job.status == VoiceJobStatus.DONE
    _, total = await task_service.list_tasks(session)
    assert total == 1


async def test_already_done_job_is_idempotent(session, user, voice_job, notify):
    await transcribe_voice(_ctx(StubBot(), FakeTranscriber("once")), voice_job.id)
    await transcribe_voice(_ctx(StubBot(), FakeTranscriber("twice")), voice_job.id)
    _, total = await task_service.list_tasks(session)
    assert total == 1 and notify.await_count == 1


async def test_empty_transcript_fails_permanently(session, voice_job, notify, event_stream):
    await transcribe_voice(_ctx(StubBot(), FakeTranscriber("")), voice_job.id)
    await session.refresh(voice_job)
    assert voice_job.status == VoiceJobStatus.FAILED
    assert voice_job.error == "transcription_empty"
    _, total = await task_service.list_tasks(session)
    assert total == 0
    notify.assert_awaited_once()
    assert "no speech detected" in notify.await_args.args[2]
    event = await event_stream.next()
    assert event["type"] == "voice.failed" and event["error"] == "transcription_empty"


async def test_file_too_large_fails_without_download(session, voice_job, notify):
    transcriber = FakeTranscriber("x")
    await transcribe_voice(_ctx(StubBot(file_size=30 * 1024 * 1024), transcriber), voice_job.id)
    await session.refresh(voice_job)
    assert (voice_job.status, voice_job.error) == (VoiceJobStatus.FAILED, "file_too_large")
    assert transcriber.calls == []
    assert "too big" in notify.await_args.args[2]


async def test_download_error_retries_then_gives_up(session, voice_job, notify, event_stream):
    bot = StubBot(download_error=OSError("connection reset"))
    with pytest.raises(Retry):
        await transcribe_voice(_ctx(bot, FakeTranscriber("x"), job_try=1), voice_job.id)
    await session.refresh(voice_job)
    assert (voice_job.status, voice_job.error, voice_job.attempts) == (
        VoiceJobStatus.QUEUED,
        "download_failed",
        1,
    )
    notify.assert_not_awaited()

    with pytest.raises(Retry):
        await transcribe_voice(_ctx(bot, FakeTranscriber("x"), job_try=2), voice_job.id)

    await transcribe_voice(_ctx(bot, FakeTranscriber("x"), job_try=3), voice_job.id)  # no raise
    await session.refresh(voice_job)
    assert (voice_job.status, voice_job.error, voice_job.attempts) == (
        VoiceJobStatus.FAILED,
        "download_failed",
        3,
    )
    notify.assert_awaited_once()
    assert "could not download" in notify.await_args.args[2]
    assert (await event_stream.next())["error"] == "download_failed"


async def test_backend_error_is_retryable(session, voice_job, notify):
    with pytest.raises(Retry):
        await transcribe_voice(_ctx(StubBot(), FakeTranscriber("fail")), voice_job.id)
    await session.refresh(voice_job)
    assert voice_job.error == "transcription_failed"


async def test_long_transcript_is_truncated_to_title_limit(session, voice_job, notify):
    await transcribe_voice(_ctx(StubBot(), FakeTranscriber("x" * 900)), voice_job.id)
    items, _ = await task_service.list_tasks(session)
    assert len(items[0].title) == 500


async def test_notification_edits_message(session):
    bot = StubBot()
    await send_notification({"bot": bot, "job_try": 1}, 1, 7, "hello")
    assert bot.edited == [(1, 7, "hello")] and bot.sent == []


async def test_notification_falls_back_to_send_when_edit_fails(session):
    bot = StubBot()
    bot.edit_error = TelegramBadRequest(method=None, message="message to edit not found")
    await send_notification({"bot": bot, "job_try": 1}, 1, 7, "hello")
    assert bot.edited == [] and bot.sent == [(1, "hello")]


async def test_notification_sends_when_no_message_id(session):
    bot = StubBot()
    await send_notification({"bot": bot, "job_try": 1}, 1, None, "hi")
    assert bot.sent == [(1, "hi")]


async def test_notification_retries_on_network_error(session):
    bot = StubBot()
    bot.edit_error = TelegramNetworkError(method=None, message="timeout")
    bot.send_message = AsyncMock(side_effect=bot.edit_error)
    with pytest.raises(Retry):
        await send_notification({"bot": bot, "job_try": 1}, 1, 7, "hello")
    with pytest.raises(TelegramNetworkError):
        await send_notification({"bot": bot, "job_try": 5}, 1, 7, "hello")
