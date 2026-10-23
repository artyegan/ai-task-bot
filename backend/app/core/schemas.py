"""Pydantic schemas: the JSON shapes shared by REST responses and WebSocket events."""

from datetime import UTC, datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, field_serializer, model_validator

from app.core.models import MAX_TITLE_LENGTH, TaskSource, TaskStatus

# Whitespace is stripped before the length checks, so "   " is rejected, not stored empty.
Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_LENGTH)
]


def iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    username: str | None
    first_name: str | None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: int
    title: str
    description: str | None
    status: TaskStatus
    source: TaskSource
    user: UserOut
    telegram_message_id: int | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, value: datetime) -> str:
        return iso_z(value)


class TaskList(BaseModel):
    items: list[TaskOut]
    total: int


class UserList(BaseModel):
    items: list[UserOut]


class TaskCreate(BaseModel):
    title: Title
    description: str | None = None
    user_id: int


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None
    title: Title | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one of status, title, description is required")
        return self
