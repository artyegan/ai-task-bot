"""send_notification(chat_id, message_id, text): edit our earlier reply, or send a new message.

Separate from transcription so a Telegram outage never blocks the model, and vice versa.
Retries up to 5 times with backoff on network errors / rate limits.
"""

from typing import Any

from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter
from arq import Retry

from app.core.logging import get_logger

log = get_logger("worker.notify")

MAX_TRIES = 5


async def send_notification(
    ctx: dict[str, Any], chat_id: int, message_id: int | None, text: str
) -> None:
    bot = ctx["bot"]
    attempt = ctx.get("job_try", 1)
    try:
        if message_id is not None:
            try:
                await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
                return
            except TelegramBadRequest as exc:
                # e.g. message deleted by the user or too old to edit: send a fresh one instead
                log.info("notify.edit_fallback", chat_id=chat_id, detail=str(exc))
        await bot.send_message(chat_id, text)
    except TelegramRetryAfter as exc:
        if attempt >= MAX_TRIES:
            raise
        raise Retry(defer=exc.retry_after) from exc
    except TelegramNetworkError as exc:
        if attempt >= MAX_TRIES:
            raise
        raise Retry(defer=min(2**attempt, 30)) from exc
