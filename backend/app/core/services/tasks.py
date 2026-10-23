"""Task service: the single place where tasks and users are created or changed.

Every write commits, then publishes the matching event (never before the commit).
"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import events, messages, queue
from app.core.exceptions import TaskNotFound, UserNotFound
from app.core.models import Task, TaskSource, TaskStatus, User, utcnow


async def get_or_create_user(
    session: AsyncSession, telegram_id: int, username: str | None, first_name: str | None
) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        session.add(user)
    elif (user.username, user.first_name) != (username, first_name):
        user.username, user.first_name = username, first_name
    await session.commit()
    return user


async def list_users(session: AsyncSession) -> Sequence[User]:
    return (await session.scalars(select(User).order_by(User.id))).all()


async def list_tasks(
    session: AsyncSession,
    *,
    statuses: Sequence[TaskStatus] = (),
    user_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[Sequence[Task], int]:
    query = select(Task)
    if statuses:
        query = query.where(Task.status.in_(statuses))
    if user_id is not None:
        query = query.where(Task.user_id == user_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = await session.scalars(
        query.order_by(Task.created_at.desc(), Task.id.desc()).limit(limit).offset(offset)
    )
    return items.all(), total


async def get_task(session: AsyncSession, task_id: int) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise TaskNotFound(task_id)
    return task


async def get_user_task(session: AsyncSession, user_id: int, number: int) -> Task:
    """Look a task up by its per-user number (what the bot shows)."""
    task = await session.scalar(
        select(Task).where(Task.user_id == user_id, Task.number == number)
    )
    if task is None:
        raise TaskNotFound(number)
    return task


async def create_task(
    session: AsyncSession,
    *,
    user_id: int,
    title: str,
    description: str | None = None,
    source: TaskSource = TaskSource.TEXT,
    telegram_message_id: int | None = None,
) -> Task:
    # Lock the owner row so concurrent creates for the same user get distinct numbers.
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise UserNotFound(user_id)
    next_number = await session.scalar(
        select(func.coalesce(func.max(Task.number), 0) + 1).where(Task.user_id == user_id)
    )
    task = Task(
        user_id=user_id,
        number=next_number,
        title=title.strip(),
        description=description,
        source=source,
        telegram_message_id=telegram_message_id,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)  # load the joined user for the event payload
    await events.publish(events.task_event("task.created", task))
    return task


async def update_task(
    session: AsyncSession,
    task_id: int,
    *,
    status: TaskStatus | None = None,
    title: str | None = None,
    description: str | None = None,
    notify_owner: bool = False,
) -> Task:
    task = await get_task(session, task_id)
    status_changed = status is not None and status != task.status
    if status is not None:
        task.status = status
    if title is not None:
        task.title = title.strip()
    if description is not None:
        task.description = description
    task.updated_at = utcnow()
    await session.commit()
    await events.publish(events.task_event("task.updated", task))
    if status_changed and notify_owner:
        await queue.enqueue_notification(task.user.telegram_id, None, messages.status_changed(task))
    return task


async def delete_task(session: AsyncSession, task_id: int) -> None:
    task = await get_task(session, task_id)
    await session.delete(task)
    await session.commit()
    await events.publish(events.task_deleted_event(task_id))
