"""Work-queue models — typed work items with state machine."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class WorkItemStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    DEFERRED = "deferred"


class WorkItemPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WorkItemType(StrEnum):
    SEND_MESSAGE = "send_message"
    SCHEDULE_MEETING = "schedule_meeting"
    CONDUCT_INTERVIEW = "conduct_interview"
    REVIEW_ARTIFACT = "review_artifact"
    APPROVE_ARTIFACT = "approve_artifact"
    EXECUTE_IN_SYSTEM = "execute_in_system"
    ANSWER_QUESTION = "answer_question"
    MAKE_DECISION = "make_decision"
    AGENT_FOLLOW_UP = "agent_follow_up"
    AGENT_REFRESH = "agent_refresh"


class WorkItem(BaseModel):
    """A rich work-queue item."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    id: str
    type: WorkItemType
    assignee: Literal["human", "agent"]
    status: WorkItemStatus
    priority: WorkItemPriority
    title: str
    description: str
    payload: dict[str, object] = {}
    related_artifact_ids: list[str] = []
    related_question_ids: list[str] = []
    related_stakeholder_ids: list[str] = []
    blocks: list[str] = []
    blocked_by: list[str] = []
    created_at: datetime
    updated_at: datetime
    deadline: datetime | None = None
    completed_at: datetime | None = None
    completion_note: str | None = None
    return_payload: dict[str, object] | None = None
    rationale: str


# Valid state transitions
_VALID_TRANSITIONS: dict[WorkItemStatus, set[WorkItemStatus]] = {
    WorkItemStatus.QUEUED: {
        WorkItemStatus.IN_PROGRESS,
        WorkItemStatus.REJECTED,
        WorkItemStatus.DEFERRED,
        WorkItemStatus.SUPERSEDED,
    },
    WorkItemStatus.IN_PROGRESS: {
        WorkItemStatus.DONE,
        WorkItemStatus.BLOCKED,
        WorkItemStatus.DEFERRED,
        WorkItemStatus.SUPERSEDED,
    },
    WorkItemStatus.BLOCKED: {
        WorkItemStatus.IN_PROGRESS,
        WorkItemStatus.SUPERSEDED,
    },
    WorkItemStatus.DEFERRED: {
        WorkItemStatus.QUEUED,
        WorkItemStatus.SUPERSEDED,
    },
    WorkItemStatus.DONE: {
        WorkItemStatus.SUPERSEDED,
    },
    WorkItemStatus.REJECTED: {
        WorkItemStatus.SUPERSEDED,
    },
    WorkItemStatus.SUPERSEDED: set(),
}


def is_valid_transition(from_status: WorkItemStatus, to_status: WorkItemStatus) -> bool:
    """Check if a state transition is valid."""
    return to_status in _VALID_TRANSITIONS.get(from_status, set())
