"""Request and response bodies. These mirror `components.schemas` in openapi.yaml."""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SYMBOL_PATTERN = r"^[A-Za-z]{1,10}(\.[A-Za-z]{1,2})?$"
MAX_QUESTION_LENGTH = 2000


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", "updated_at", mode="after", check_fields=False)
    @classmethod
    def _assume_utc(cls, value: datetime) -> datetime:
        # SQLite drops timezone info; every timestamp we store is UTC.
        return value if value.tzinfo else value.replace(tzinfo=UTC)


class Error(BaseModel):
    code: str
    message: str


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    version: str
    commit: str | None = None


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] | None = None


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=80)


class SessionSummary(_Out):
    id: uuid.UUID
    title: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class Message(_Out):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    tool_calls: list[ToolCall]
    created_at: datetime


class SessionDetail(SessionSummary):
    messages: list[Message]


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must not be blank")
        return value


class ChatTurn(BaseModel):
    user_message: Message
    assistant_message: Message


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(pattern=SYMBOL_PATTERN)
    note: str | None = Field(default=None, max_length=200)


class WatchlistItem(_Out):
    symbol: str
    note: str | None
    created_at: datetime
