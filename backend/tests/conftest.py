"""Tests run against the real Postgres and Redis from docker-compose (profile `test`).

DATABASE_URL points at a dedicated database which is created on demand; REDIS_URL at a
dedicated db index. Both are wiped between tests.
"""

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.main import app
from app.core import events, models
from app.core.config import get_settings
from app.core.db import Base, SessionFactory, engine
from app.core.redis import redis
from app.core.services import tasks as task_service


async def _ensure_database() -> None:
    url = make_url(get_settings().database_url)
    conn = await asyncpg.connect(
        host=url.host, port=url.port, user=url.username, password=url.password, database="postgres"
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", url.database)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def _database():
    await _ensure_database()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    await redis.aclose()


@pytest.fixture(autouse=True)
async def _clean():
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE voice_jobs, tasks, users RESTART IDENTITY CASCADE"))
    await redis.flushdb()


@pytest.fixture
async def session() -> AsyncSession:
    async with SessionFactory() as s:
        yield s


@pytest.fixture
async def user(session: AsyncSession) -> models.User:
    return await task_service.get_or_create_user(session, 123456789, "alice", "Alice")


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class EventStream:
    """Subscribes to the Redis events channel; `next()` returns the next published event."""

    def __init__(self, pubsub) -> None:
        self._pubsub = pubsub

    async def next(self, timeout: float = 3.0) -> dict:
        import asyncio
        import json

        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            msg = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if msg:
                return json.loads(msg["data"])
        raise AssertionError("no event published")


@pytest.fixture
async def event_stream():
    pubsub = redis.pubsub()
    await pubsub.subscribe(events.CHANNEL)
    await pubsub.get_message(timeout=1)  # subscribe confirmation
    yield EventStream(pubsub)
    await pubsub.aclose()
