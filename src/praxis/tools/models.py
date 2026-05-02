"""Tool subsystem data models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ToolResult(BaseModel):
    """Result returned by a tool function."""

    model_config = ConfigDict(extra="forbid")

    content: str
    data: dict[str, object] = {}


class ToolResultMessage(BaseModel):
    """A tool result paired with the call ID for returning to the LLM."""

    model_config = ConfigDict(extra="forbid")

    tool_call_id: str
    content: str
    is_error: bool = False


class ApprovalDecision(StrEnum):
    """Outcome of a dangerous-tool approval check."""

    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
