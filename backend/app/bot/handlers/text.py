"""Plain text message -> task."""

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages
from app.core.models import MAX_TITLE_LENGTH, TaskSource, User
from app.core.services import tasks as task_service

router = Router(name="text")


@router.message(F.text)
async def create_text_task(message: Message, session: AsyncSession, user: User) -> None:
    title = (message.text or "").strip()
    if not title:
        return
    if len(title) > MAX_TITLE_LENGTH:
        await message.answer(messages.TITLE_TOO_LONG.format(max_chars=MAX_TITLE_LENGTH))
        return
    task = await task_service.create_task(
        session,
        user_id=user.id,
        title=title,
        source=TaskSource.TEXT,
        telegram_message_id=message.message_id,
    )
    await message.answer(messages.TEXT_TASK_CREATED.format(number=task.number, title=task.title))
