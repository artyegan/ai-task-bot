import asyncio
import json

import pytest

from app.core import events
from app.core.exceptions import TaskNotFound, UserNotFound
from app.core.models import TaskSource, TaskStatus
from app.core.redis import redis
from app.core.services import tasks as task_service


async def _subscribe():
    pubsub = redis.pubsub()
    await pubsub.subscribe(events.CHANNEL)
    await pubsub.get_message(timeout=1)  # the subscribe confirmation
    return pubsub


async def _next_event(pubsub) -> dict:
    for _ in range(20):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
        if msg:
            return json.loads(msg["data"])
        await asyncio.sleep(0.05)
    raise AssertionError("no event published")


async def test_get_or_create_user_is_idempotent_and_updates_profile(session):
    a = await task_service.get_or_create_user(session, 1, "a", "A")
    b = await task_service.get_or_create_user(session, 1, "b", "B")
    assert a.id == b.id
    assert (b.username, b.first_name) == ("b", "B")


async def test_create_task_publishes_event(session, user):
    pubsub = await _subscribe()
    task = await task_service.create_task(
        session,
        user_id=user.id,
        title="  Buy milk ",
        source=TaskSource.VOICE,
        telegram_message_id=7,
    )
    assert task.title == "Buy milk"
    assert task.status == TaskStatus.PENDING
    assert task.user.telegram_id == 123456789

    event = await _next_event(pubsub)
    assert event["type"] == "task.created"
    assert event["task"]["id"] == task.id
    assert event["task"]["source"] == "voice"
    assert event["task"]["user"]["username"] == "alice"
    assert event["ts"].endswith("Z")
    await pubsub.aclose()


async def test_numbers_are_per_user_and_survive_deletes(session, user):
    other = await task_service.get_or_create_user(session, 2, "o", "O")
    a1 = await task_service.create_task(session, user_id=user.id, title="a1")
    b1 = await task_service.create_task(session, user_id=other.id, title="b1")
    a2 = await task_service.create_task(session, user_id=user.id, title="a2")
    assert (a1.number, a2.number, b1.number) == (1, 2, 1)
    # deleting the latest task frees its number only as "max + 1" (no holes are backfilled)
    await task_service.delete_task(session, a2.id)
    a3 = await task_service.create_task(session, user_id=user.id, title="a3")
    assert a3.number == 2
    found = await task_service.get_user_task(session, other.id, 1)
    assert found.id == b1.id
    with pytest.raises(TaskNotFound):
        await task_service.get_user_task(session, other.id, 2)


async def test_concurrent_creates_get_distinct_numbers(user):
    from app.core.db import SessionFactory

    async def create(i: int):
        async with SessionFactory() as s:
            return (await task_service.create_task(s, user_id=user.id, title=f"t{i}")).number

    numbers = await asyncio.gather(*(create(i) for i in range(8)))
    assert sorted(numbers) == list(range(1, 9))


async def test_create_task_unknown_user(session):
    with pytest.raises(UserNotFound):
        await task_service.create_task(session, user_id=999, title="x")


async def test_list_filters_and_orders_newest_first(session, user):
    t1 = await task_service.create_task(session, user_id=user.id, title="one")
    t2 = await task_service.create_task(session, user_id=user.id, title="two")
    await task_service.update_task(session, t1.id, status=TaskStatus.COMPLETED)

    items, total = await task_service.list_tasks(session)
    assert total == 2 and [t.id for t in items] == [t2.id, t1.id]

    items, total = await task_service.list_tasks(session, statuses=[TaskStatus.COMPLETED])
    assert total == 1 and items[0].id == t1.id

    items, total = await task_service.list_tasks(session, limit=1, offset=1)
    assert total == 2 and [t.id for t in items] == [t1.id]


async def test_update_status_publishes_event(session, user):
    task = await task_service.create_task(session, user_id=user.id, title="one")
    pubsub = await _subscribe()
    updated = await task_service.update_task(session, task.id, status=TaskStatus.IN_PROGRESS)
    assert updated.status == TaskStatus.IN_PROGRESS
    assert updated.updated_at >= task.created_at
    event = await _next_event(pubsub)
    assert event["type"] == "task.updated" and event["task"]["status"] == "in_progress"
    await pubsub.aclose()


async def test_publish_failure_does_not_fail_the_write(session, user, monkeypatch):
    from app.core import events

    async def broken_publish(*_a, **_k):
        raise ConnectionError("redis down")

    monkeypatch.setattr(events.redis, "publish", broken_publish)
    task = await task_service.create_task(session, user_id=user.id, title="saved anyway")
    assert task.id and (await task_service.get_task(session, task.id)).title == "saved anyway"


async def test_delete_task(session, user):
    task = await task_service.create_task(session, user_id=user.id, title="bye")
    pubsub = await _subscribe()
    await task_service.delete_task(session, task.id)
    event = await _next_event(pubsub)
    assert event["type"] == "task.deleted" and event["task_id"] == task.id
    assert event["ts"].endswith("Z")
    with pytest.raises(TaskNotFound):
        await task_service.get_task(session, task.id)
    await pubsub.aclose()
