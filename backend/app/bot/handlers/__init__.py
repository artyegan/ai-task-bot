from aiogram import Router

from app.bot.handlers import commands, text, voice

router = Router(name="root")
router.include_router(commands.router)
router.include_router(text.router)
router.include_router(voice.router)  # last: voice/audio, then the catch-all for other types
