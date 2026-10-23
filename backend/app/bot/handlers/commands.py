"""/start, /list, /status, /doing, /done, /pending."""

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages
from app.core.exceptions import TaskNotFound
from app.core.models import TaskStatus, User
from app.core.services import tasks as task_service

router = Router(name="commands")


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(messages.START)


@router.message(Command("list"))
async def list_open_tasks(message: Message, session: AsyncSession, user: User) -> None:
    items, _ = await task_service.list_tasks(
        session,
        statuses=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS],
        user_id=user.id,
        limit=50,
    )
    if not items:
        await message.answer(messages.NO_OPEN_TASKS)
        return
    lines = [
        messages.LIST_LINE.format(
            number=t.number, status=messages.STATUS_LABELS[t.status], title=t.title
        )
        for t in reversed(items)  # oldest first reads naturally as a list
    ]
    await message.answer(messages.LIST_HEADER + "\n".join(lines))


def _task_number(command: CommandObject) -> int | None:
    """`/cmd 3` or `/cmd #3` -> 3; anything else -> None."""
    arg = (command.args or "").strip().lstrip("#")
    return int(arg) if arg.isdigit() else None


@router.message(Command("status"))
async def show_status(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    number = _task_number(command)
    if number is None:
        await message.answer(messages.USAGE_STATUS)
        return
    try:
        task = await task_service.get_user_task(session, user.id, number)
    except TaskNotFound:
        await message.answer(messages.TASK_NOT_FOUND.format(number=number))
        return
    await message.answer(
        messages.TASK_STATUS.format(
            number=task.number,
            title=task.title,
            status=messages.STATUS_LABELS[task.status],
            created=task.created_at.strftime("%Y-%m-%d %H:%M UTC"),
            source=task.source.value,
        )
    )


async def _set_status(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    user: User,
    status: TaskStatus,
    usage: str,
    confirmation: str,
) -> None:
    number = _task_number(command)
    if number is None:
        await message.answer(usage)
        return
    try:
        task = await task_service.get_user_task(session, user.id, number)  # scoped to the sender
        task = await task_service.update_task(session, task.id, status=status)
    except TaskNotFound:
        await message.answer(messages.TASK_NOT_FOUND.format(number=number))
        return
    await message.answer(confirmation.format(number=task.number, title=task.title))


@router.message(Command("doing"))
async def mark_in_progress(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    await _set_status(
        message,
        command,
        session,
        user,
        TaskStatus.IN_PROGRESS,
        messages.USAGE_DOING,
        messages.TASK_IN_PROGRESS,
    )


@router.message(Command("pending"))
async def mark_pending(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    await _set_status(
        message,
        command,
        session,
        user,
        TaskStatus.PENDING,
        messages.USAGE_PENDING,
        messages.TASK_PENDING,
    )


@router.message(Command("done"))
async def mark_done(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    await _set_status(
        message,
        command,
        session,
        user,
        TaskStatus.COMPLETED,
        messages.USAGE_DONE,
        messages.TASK_DONE,
    )


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer(messages.UNKNOWN_COMMAND)
