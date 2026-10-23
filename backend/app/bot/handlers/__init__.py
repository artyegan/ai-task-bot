from aiogram import Router

from app.bot.handlers import commands, text

router = Router(name="root")
router.include_router(commands.router)
router.include_router(text.router)  # last: catches everything that is not a command
