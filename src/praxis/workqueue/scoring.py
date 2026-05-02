"""Work-queue prioritization — composite score for daily views."""

from __future__ import annotations

from datetime import UTC, datetime

from .models import WorkItem, WorkItemPriority, WorkItemStatus

# Default weights
_PRIORITY_WEIGHTS: dict[WorkItemPriority, float] = {
    WorkItemPriority.CRITICAL: 100.0,
    WorkItemPriority.HIGH: 75.0,
    WorkItemPriority.MEDIUM: 50.0,
    WorkItemPriority.LOW: 25.0,
}

_DEADLINE_URGENCY_WEIGHT = 2.0  # points per day remaining (inverse)
_BLOCKING_WEIGHT = 10.0  # per item blocked
_AGE_DECAY_WEIGHT = 0.5  # points per day since creation


def score_item(item: WorkItem, *, now: datetime | None = None) -> float:
    """Compute a composite priority score (higher = more urgent)."""
    if now is None:
        now = datetime.now(UTC)

    score = _PRIORITY_WEIGHTS.get(item.priority, 50.0)

    # Deadline urgency: more points as deadline approaches
    if item.deadline:
        days_remaining = (item.deadline - now).total_seconds() / 86400.0
        if days_remaining <= 0:
            score += 50.0  # overdue bonus
        elif days_remaining <= 7:
            score += _DEADLINE_URGENCY_WEIGHT * (7 - days_remaining)

    # Blocking count
    score += len(item.blocks) * _BLOCKING_WEIGHT

    # Age decay: older items get a small boost
    age_days = (now - item.created_at).total_seconds() / 86400.0
    score += age_days * _AGE_DECAY_WEIGHT

    return score


def prioritize(
    items: list[WorkItem],
    *,
    now: datetime | None = None,
    active_only: bool = True,
) -> list[WorkItem]:
    """Sort items by composite score, highest first.

    By default, only includes QUEUED and IN_PROGRESS items.
    """
    if active_only:
        active_statuses = {WorkItemStatus.QUEUED, WorkItemStatus.IN_PROGRESS}
        items = [i for i in items if i.status in active_statuses]

    scored = [(score_item(i, now=now), i) for i in items]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]
