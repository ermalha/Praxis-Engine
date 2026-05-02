"""Pydantic models for SQLite-backed storage entities."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MessageRole(StrEnum):
    """Roles for conversation messages."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class WorkItemStatus(StrEnum):
    """Work-item lifecycle states."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkItemPriority(StrEnum):
    """Work-item priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Session(BaseModel):
    """A conversation session."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    id: str
    parent_id: str | None = None
    profile: str
    started_at: datetime
    ended_at: datetime | None = None
    summary: str | None = None
    metadata: dict[str, object] = {}


class Message(BaseModel):
    """A single message within a session."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    id: str
    session_id: str
    turn: int
    role: MessageRole
    content: str
    tool_calls_json: str | None = None
    created_at: datetime


class FTSResult(BaseModel):
    """A full-text search result from messages_fts."""

    model_config = ConfigDict(extra="forbid")

    message_id: str
    session_id: str
    role: str
    content: str
    rank: float


class WorkItem(BaseModel):
    """A work-queue item."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    id: str
    type: str
    status: WorkItemStatus
    priority: WorkItemPriority
    payload: dict[str, object]
    created_at: datetime
    updated_at: datetime
    deadline: datetime | None = None
    completed_at: datetime | None = None
