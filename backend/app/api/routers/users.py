from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.schemas import UserList, UserOut
from app.core.services import tasks as task_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=UserList)
async def list_users(session: Annotated[AsyncSession, Depends(get_session)]) -> UserList:
    users = await task_service.list_users(session)
    return UserList(items=[UserOut.model_validate(u) for u in users])
