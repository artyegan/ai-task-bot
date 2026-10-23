"""Telegram bot entrypoint (long polling)."""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, ErrorEvent

from app.bot.handlers import router
from app.bot.middleware import DbUserMiddleware
from app.bot.retry import RetryOnNetworkError
from app.core import messages, queue
from app.core.config import get_settings
from app.core.db import engine
from app.core.logging import configure_logging, get_logger
from app.core.redis import redis

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger("bot")

COMMANDS = [
    BotCommand(command="start", description="What this bot does"),
    BotCommand(command="list", description="Show my open tasks"),
    BotCommand(command="status", description="Show one task: /status <number>"),
    BotCommand(command="doing", description="Mark a task in progress: /doing <number>"),
    BotCommand(command="done", description="Mark a task completed: /done <number>"),
    BotCommand(command="pending", description="Move a task back to pending: /pending <number>"),
]


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.middleware(DbUserMiddleware())
    dp.include_router(router)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> None:
        # Log and tell the user instead of silently dropping the update.
        log.exception("bot.handler_error", error=str(event.exception))
        message = event.update.message
        if message is not None:
            try:
                await message.answer(messages.SOMETHING_WENT_WRONG)
            except Exception:  # noqa: BLE001 - best effort
                pass

    return dp


async def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set (see .env.example)")
    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=None))
    bot.session.middleware(RetryOnNetworkError())
    dp = build_dispatcher()
    me = await bot.get_me()
    await bot.set_my_commands(COMMANDS)
    log.info("bot.start", username=me.username)
    try:
        await dp.start_polling(bot, handle_signals=True)
    finally:
        await bot.session.close()
        await queue.close_pool()
        await engine.dispose()
        await redis.aclose()
        log.info("bot.stop")


if __name__ == "__main__":
    asyncio.run(main())
