"""Retry transient Telegram network errors at the client level.

A fresh container's first outbound connection, a DNS blip or a dropped socket must not turn
a successfully saved task into a "something went wrong" reply. Applies to every Bot call
(replies, edits, command setup, worker notifications). getUpdates is excluded: polling has
its own retry loop in aiogram.
"""

import asyncio
from typing import Any

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetUpdates, TelegramMethod

from app.core.logging import get_logger

log = get_logger("telegram")


class RetryOnNetworkError(BaseRequestMiddleware):
    def __init__(self, attempts: int = 3, base_delay: float = 0.5) -> None:
        self.attempts = attempts
        self.base_delay = base_delay

    async def __call__(self, make_request: Any, bot: Bot, method: TelegramMethod[Any]) -> Any:
        if isinstance(method, GetUpdates):
            return await make_request(bot, method)
        for attempt in range(1, self.attempts + 1):
            try:
                return await make_request(bot, method)
            except TelegramNetworkError as exc:
                if attempt == self.attempts:
                    raise
                delay = self.base_delay * 2 ** (attempt - 1)
                log.warning(
                    "telegram.retry",
                    method=type(method).__name__,
                    attempt=attempt,
                    retry_in=delay,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
        raise AssertionError("unreachable")
