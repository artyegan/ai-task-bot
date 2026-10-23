"""Feeds real Telegram updates through the Dispatcher: middleware, router order and handlers
all run as in production; only the Telegram HTTP session is replaced by a recorder."""

import time
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import EditMessageText, SendMessage, TelegramMethod
from aiogram.types import Chat, Message

from app.bot.main import build_dispatcher
from app.core import messages
from app.core.redis import redis
from app.core.services import tasks as task_service


class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[str] = []

    async def close(self) -> None:
        return None

    async def stream_content(self, *_a: Any, **_k: Any):  # pragma: no cover - unused
        raise NotImplementedError
        yield b""

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None):
        if isinstance(method, SendMessage):
            self.sent.append(method.text)
            return Message(
                message_id=1000 + len(self.sent),
                date=int(time.time()),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        if isinstance(method, EditMessageText):
            self.sent.append(f"[edit] {method.text}")
            return True
        raise NotImplementedError(type(method).__name__)


CHAT = {"id": 123456789, "type": "private"}
FROM = {"id": 123456789, "is_bot": False, "first_name": "Alice", "username": "alice"}


def _update(uid: int, **message: Any) -> dict:
    return {
        "update_id": uid,
        "message": {
            "message_id": uid,
            "date": int(time.time()),
            "chat": CHAT,
            "from": FROM,
            **message,
        },
    }


@pytest.fixture(scope="session")
def dp():
    # Routers are module-level objects and can be attached to one Dispatcher only.
    return build_dispatcher()


@pytest.fixture
async def bot(dp):
    b = Bot(token="42:TEST", session=RecordingSession())
    b.dp = dp  # type: ignore[attr-defined]
    yield b
    await b.session.close()


async def _feed(bot: Bot, **message: Any) -> list[str]:
    session: RecordingSession = bot.session  # type: ignore[assignment]
    before = len(session.sent)
    await bot.dp.feed_raw_update(bot, _update(before + 1, **message))  # type: ignore[attr-defined]
    return session.sent[before:]


async def test_start_registers_user_and_replies(bot, session):
    assert await _feed(bot, text="/start") == [messages.START]
    users = await task_service.list_users(session)
    assert [u.telegram_id for u in users] == [123456789]


async def test_text_becomes_task_and_commands_still_work(bot, session):
    assert await _feed(bot, text="Buy milk") == ["✅ Task #1 created: Buy milk"]
    assert await _feed(bot, text="/list") == ["📋 Your open tasks:\n#1 [Pending] Buy milk"]
    assert await _feed(bot, text="/done #1") == ["✅ Task #1 completed: Buy milk"]  # "#" allowed
    assert await _feed(bot, text="/list") == [messages.NO_OPEN_TASKS]


async def test_unknown_command_is_not_turned_into_a_task(bot, session):
    assert await _feed(bot, text="/frobnicate") == [messages.UNKNOWN_COMMAND]
    _, total = await task_service.list_tasks(session)
    assert total == 0


async def test_voice_is_acknowledged_and_queued(bot, session):
    voice = {"file_id": "F1", "file_unique_id": "U1", "duration": 3, "file_size": 5000}
    assert await _feed(bot, voice=voice) == [messages.VOICE_RECEIVED]
    assert await redis.zcard("arq:queue") == 1


async def test_sticker_gets_a_hint(bot, session):
    sticker = {
        "file_id": "S1",
        "file_unique_id": "SU1",
        "type": "regular",
        "width": 512,
        "height": 512,
        "is_animated": False,
        "is_video": False,
    }
    assert await _feed(bot, sticker=sticker) == [messages.UNSUPPORTED_MESSAGE]
