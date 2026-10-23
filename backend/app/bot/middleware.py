"""Per-message middleware: opens a DB session, resolves the Telegram user to our User row,
and logs how long each message took to handle (the bot's feedback speed is a design goal)."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.core.db import SessionFactory
from app.core.logging import get_logger
from app.core.services import tasks as task_service

log = get_logger("bot")


def _kind(message: Message) -> str:
    if message.text:
        return "command" if message.text.startswith("/") else "text"
    if message.voice or message.audio:
        return "voice"
    return "other"


class DbUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        started = time.perf_counter()
        async with SessionFactory() as session:
            data["session"] = session
            if isinstance(event, Message) and event.from_user is not None:
                data["user"] = await task_service.get_or_create_user(
                    session,
                    event.from_user.id,
                    event.from_user.username,
                    event.from_user.first_name,
                )
            try:
                return await handler(event, data)
            finally:
                if isinstance(event, Message):
                    log.info(
                        "bot.handled",
                        kind=_kind(event),
                        ms=round((time.perf_counter() - started) * 1000),
                        user_id=data.get("user").id if data.get("user") else None,
                    )
