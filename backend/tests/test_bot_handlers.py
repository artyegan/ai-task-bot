"""Bot handlers are called directly with a stubbed Message; DB, Redis and the service are real."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.filters import CommandObject

from app.bot.handlers import commands, text
from app.core import messages
from app.core.models import TaskStatus
from app.core.services import tasks as task_service


def _message(body: str, message_id: int = 10) -> SimpleNamespace:
    return SimpleNamespace(text=body, message_id=message_id, answer=AsyncMock())


async def test_text_creates_task_and_replies(session, user):
    msg = _message("  Buy milk  ", message_id=77)
    await text.create_text_task(msg, session, user)
    items, total = await task_service.list_tasks(session)
    assert total == 1
    assert items[0].title == "Buy milk" and items[0].telegram_message_id == 77
    assert items[0].number == 1
    msg.answer.assert_awaited_once_with("✅ Task #1 created: Buy milk")


async def test_text_too_long_is_rejected(session, user):
    msg = _message("x" * 501)
    await text.create_text_task(msg, session, user)
    _, total = await task_service.list_tasks(session)
    assert total == 0
    msg.answer.assert_awaited_once_with("❌ That's too long for a task title (max 500 characters).")


async def test_list_empty_then_with_tasks(session, user):
    msg = _message("/list")
    await commands.list_open_tasks(msg, session, user)
    msg.answer.assert_awaited_once_with(messages.NO_OPEN_TASKS)

    t1 = await task_service.create_task(session, user_id=user.id, title="first")
    t2 = await task_service.create_task(session, user_id=user.id, title="second")
    await task_service.update_task(session, t2.id, status=TaskStatus.IN_PROGRESS)
    done = await task_service.create_task(session, user_id=user.id, title="old")
    await task_service.update_task(session, done.id, status=TaskStatus.COMPLETED)

    msg = _message("/list")
    await commands.list_open_tasks(msg, session, user)
    reply = msg.answer.await_args.args[0]
    assert reply.splitlines()[1:] == [
        f"#{t1.number} [Pending] first",
        f"#{t2.number} [In Progress] second",
    ]


async def test_done_usage_and_not_found(session, user):
    msg = _message("/done")
    await commands.mark_done(msg, CommandObject(args=None), session, user)
    msg.answer.assert_awaited_once_with(messages.USAGE_DONE)

    msg = _message("/doing x")
    await commands.mark_in_progress(msg, CommandObject(args="x"), session, user)
    msg.answer.assert_awaited_once_with(messages.USAGE_DOING)

    msg = _message("/done 999")
    await commands.mark_done(msg, CommandObject(args="999"), session, user)
    msg.answer.assert_awaited_once_with("❌ Task #999 not found.")


async def test_done_cannot_touch_other_users_task(session, user):
    other = await task_service.get_or_create_user(session, 42, "other", "Other")
    task = await task_service.create_task(session, user_id=other.id, title="theirs")
    assert task.number == 1  # numbering is per user, and the sender has no task #1
    msg = _message("/done 1")
    await commands.mark_done(msg, CommandObject(args="1"), session, user)
    msg.answer.assert_awaited_once_with("❌ Task #1 not found.")
    assert (await task_service.get_task(session, task.id)).status == TaskStatus.PENDING
