"""Audit event Pydantic model."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AuditEvent(BaseModel):
    """An immutable, structured audit log entry."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    event_id: str
    timestamp: datetime
    profile: str
    engagement: str | None = None
    actor: Literal["agent", "human", "system"] = "system"
    component: str
    event_type: str
    subject_id: str | None = None
    payload: dict[str, object] = {}
    correlation_id: str | None = None
