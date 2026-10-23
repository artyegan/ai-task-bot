"""/start, /list, /done."""

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


@router.message(Command("done"))
async def mark_done(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    arg = (command.args or "").strip().lstrip("#")
    if not arg.isdigit():
        await message.answer(messages.USAGE_DONE)
        return
    number = int(arg)
    try:
        task = await task_service.get_user_task(session, user.id, number)  # scoped to the sender
        task = await task_service.update_task(session, task.id, status=TaskStatus.COMPLETED)
    except TaskNotFound:
        await message.answer(messages.TASK_NOT_FOUND.format(number=number))
        return
    await message.answer(messages.TASK_DONE.format(number=task.number, title=task.title))


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer(messages.UNKNOWN_COMMAND)
