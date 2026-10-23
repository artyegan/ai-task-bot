from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.models import TaskSource, TaskStatus
from app.core.schemas import TaskCreate, TaskList, TaskOut, TaskUpdate
from app.core.services import tasks as task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=TaskList)
async def list_tasks(
    session: Session,
    status: Annotated[list[TaskStatus], Query()] = [],  # noqa: B006 - FastAPI query default
    user_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TaskList:
    items, total = await task_service.list_tasks(
        session, statuses=status, user_id=user_id, limit=limit, offset=offset
    )
    return TaskList(items=[TaskOut.model_validate(t) for t in items], total=total)


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, session: Session) -> TaskOut:
    task = await task_service.create_task(
        session,
        user_id=body.user_id,
        title=body.title,
        description=body.description,
        source=TaskSource.TEXT,
    )
    return TaskOut.model_validate(task)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: int, session: Session) -> TaskOut:
    return TaskOut.model_validate(await task_service.get_task(session, task_id))


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(task_id: int, body: TaskUpdate, session: Session) -> TaskOut:
    task = await task_service.update_task(
        session,
        task_id,
        status=body.status,
        title=body.title,
        description=body.description,
        notify_owner=True,
    )
    return TaskOut.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, session: Session) -> Response:
    await task_service.delete_task(session, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
