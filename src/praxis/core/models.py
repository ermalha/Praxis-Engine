"""Core agent models — responses, stream events."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from praxis.transport.models import Usage


class AgentResponse(BaseModel):
    """Result of a single agent turn."""

    model_config = ConfigDict(extra="forbid")

    content: str
    tool_call_count: int = 0
    usage_total: Usage = Usage()
    session_id: str
    truncated: bool = False


class StreamEvent(BaseModel):
    """A streaming event from the agent."""

    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "text_delta",
        "tool_call_start",
        "tool_result",
        "status",
        "done",
    ]
    text: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_result: str | None = None
    is_error: bool = False
    status: str | None = None
