"""Praxis workqueue subsystem — human-gated work items."""

# Auto-register workqueue tools
import praxis.workqueue.tools as _tools  # noqa: F401
from praxis.workqueue.models import (
    WorkItem,
    WorkItemPriority,
    WorkItemStatus,
    WorkItemType,
    is_valid_transition,
)
from praxis.workqueue.repo import WorkQueueRepo
from praxis.workqueue.scoring import prioritize, score_item

__all__ = [
    "WorkItem",
    "WorkItemPriority",
    "WorkItemStatus",
    "WorkItemType",
    "WorkQueueRepo",
    "is_valid_transition",
    "prioritize",
    "score_item",
]
