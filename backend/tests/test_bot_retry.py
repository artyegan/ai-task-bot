from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetMe, GetUpdates

from app.bot.retry import RetryOnNetworkError


def _flaky(failures: int):
    calls = {"n": 0}

    async def make_request(bot, method):
        calls["n"] += 1
        if calls["n"] <= failures:
            raise TelegramNetworkError(method=method, message="Cannot connect to host")
        return "ok"

    return make_request, calls


async def test_retries_then_succeeds(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("app.bot.retry.asyncio.sleep", sleep)
    make_request, calls = _flaky(failures=2)
    assert await RetryOnNetworkError(attempts=3)(make_request, None, GetMe()) == "ok"
    assert calls["n"] == 3
    assert [c.args[0] for c in sleep.await_args_list] == [0.5, 1.0]  # exponential backoff


async def test_gives_up_after_last_attempt(monkeypatch):
    monkeypatch.setattr("app.bot.retry.asyncio.sleep", AsyncMock())
    make_request, calls = _flaky(failures=5)
    with pytest.raises(TelegramNetworkError):
        await RetryOnNetworkError(attempts=3)(make_request, None, GetMe())
    assert calls["n"] == 3


async def test_polling_requests_are_not_retried_here():
    make_request, calls = _flaky(failures=1)
    with pytest.raises(TelegramNetworkError):
        await RetryOnNetworkError()(make_request, None, GetUpdates())
    assert calls["n"] == 1
