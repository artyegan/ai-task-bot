"""Per-message middleware: opens a DB session and resolves the Telegram user to our User row."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.core.db import SessionFactory
from app.core.services import tasks as task_service


class DbUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with SessionFactory() as session:
            data["session"] = session
            if isinstance(event, Message) and event.from_user is not None:
                data["user"] = await task_service.get_or_create_user(
                    session,
                    event.from_user.id,
                    event.from_user.username,
                    event.from_user.first_name,
                )
            return await handler(event, data)
