"""Rule-based task generators for the wake cycle.

Each generator scans a facet of the engagement state and produces
:class:`CandidateTask` instances scored by urgency.  The orchestrator
collects, sorts, and picks the top-K for execution.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog

from praxis.engagement.repos.assumptions import AssumptionsConstraintsRepo
from praxis.engagement.repos.decisions import DecisionRepo
from praxis.engagement.repos.questions import OpenQuestionsRepo
from praxis.engagement.repos.risks import RiskRepo
from praxis.engagement.repos.stakeholders import StakeholderRepo
from praxis.workqueue import WorkItemStatus, WorkItemType, WorkQueueRepo

from .models import CandidateTask, StateChange

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Thresholds (sensible defaults; callers can override)
# ---------------------------------------------------------------------------

_STALL_DAYS = 3  # asked > N days ago without answer


# ---------------------------------------------------------------------------
# Individual generators
# ---------------------------------------------------------------------------


def find_stalled_questions(
    engagement_path: Path,
    *,
    stall_days: int = _STALL_DAYS,
    now: datetime | None = None,
) -> list[CandidateTask]:
    """Questions asked > *stall_days* ago that are still unanswered."""
    now = now or datetime.now(UTC)
    threshold = now - timedelta(days=stall_days)
    repo = OpenQuestionsRepo(engagement_path)

    tasks: list[CandidateTask] = []
    for q in repo.list_all(status="asked"):
        if q.asked_at is not None and q.asked_at < threshold:
            days_stalled = (now - q.asked_at).days
            tasks.append(
                CandidateTask(
                    task_type="stalled_question",
                    description=f"Follow up on stalled question: {q.question}",
                    score=50.0 + days_stalled * 5.0,
                    related_ids=[q.id, *q.candidate_answerers],
                    metadata={"question_id": q.id, "days_stalled": days_stalled},
                )
            )
    return tasks


def find_insufficient_artifacts(engagement_path: Path) -> list[CandidateTask]:
    """Sufficiency reports with INSUFFICIENT verdict that haven't been re-evaluated."""
    reports_dir = engagement_path / ".praxis" / "state" / "sufficiency-reports"
    if not reports_dir.exists():
        return []

    import json

    tasks: list[CandidateTask] = []
    for report_file in sorted(reports_dir.glob("*.json")):
        try:
            data = json.loads(report_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if data.get("verdict") == "insufficient":
            kind = data.get("artifact_kind", "unknown")
            target = data.get("artifact_target", "unknown")
            tasks.append(
                CandidateTask(
                    task_type="insufficient_artifact",
                    description=f"Re-evaluate insufficient artifact: {kind} — {target}",
                    score=40.0,
                    related_ids=[report_file.stem],
                    metadata={
                        "artifact_kind": kind,
                        "artifact_target": target,
                        "report_file": report_file.name,
                    },
                )
            )
    return tasks


def find_empty_areas(engagement_path: Path) -> list[CandidateTask]:
    """Engagement areas with no data yet (no stakeholders, no risks, etc.)."""
    tasks: list[CandidateTask] = []

    stakeholder_repo = StakeholderRepo(engagement_path)
    if not stakeholder_repo.list_all():
        tasks.append(
            CandidateTask(
                task_type="empty_stakeholders",
                description="No stakeholders identified — propose stakeholder elicitation",
                score=60.0,
            )
        )

    risk_repo = RiskRepo(engagement_path)
    if not risk_repo.list_all():
        tasks.append(
            CandidateTask(
                task_type="empty_risks",
                description="No risks identified — propose risk identification",
                score=30.0,
            )
        )

    return tasks


def find_agent_workitems(engagement_path: Path) -> list[CandidateTask]:
    """Agent work-items in QUEUED status ready for execution."""
    repo = WorkQueueRepo(engagement_path)
    items = repo.list(status=WorkItemStatus.QUEUED, assignee="agent")

    tasks: list[CandidateTask] = []
    for item in items:
        score = 35.0
        if item.type == WorkItemType.AGENT_FOLLOW_UP:
            score = 45.0
        elif item.type == WorkItemType.AGENT_REFRESH:
            score = 25.0
        tasks.append(
            CandidateTask(
                task_type="agent_workitem",
                description=f"Execute agent work-item: {item.title}",
                score=score,
                related_ids=[item.id],
                metadata={"workitem_id": item.id, "workitem_type": item.type.value},
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# State diff since last wake (D-033)
# ---------------------------------------------------------------------------


_STATE_CHANGE_TITLE_PREFIX = {
    "decision": "Review new decision",
    "constraint": "Verify new constraint impact",
    "assumption": "Validate new assumption",
    "risk": "Assess new risk",
    "question": "Acknowledge answered question",
}


def find_recent_state_changes(
    engagement_path: Path,
    *,
    since: datetime | None,
) -> list[StateChange]:
    """Diff engagement state against the prior wake's ``ended_at`` timestamp.

    When *since* is ``None`` (no prior wake report), returns an empty list —
    first wake has no diff to surface.

    Detects: new decisions/constraints/assumptions/risks (created_at>since)
    and questions transitioned to ``answered`` (answered_at>since).
    """
    if since is None:
        return []

    changes: list[StateChange] = []

    for d in DecisionRepo(engagement_path).list_all():
        if d.created_at > since:
            changes.append(
                StateChange(
                    entity_type="decision",
                    entity_id=d.id,
                    change="created",
                    title=d.title,
                    timestamp=d.created_at,
                )
            )

    ac_repo = AssumptionsConstraintsRepo(engagement_path)
    for c in ac_repo.list_constraints():
        if c.created_at > since:
            changes.append(
                StateChange(
                    entity_type="constraint",
                    entity_id=c.id,
                    change="created",
                    title=c.statement,
                    timestamp=c.created_at,
                )
            )
    for a in ac_repo.list_assumptions():
        if a.created_at > since:
            changes.append(
                StateChange(
                    entity_type="assumption",
                    entity_id=a.id,
                    change="created",
                    title=a.statement,
                    timestamp=a.created_at,
                )
            )

    for r in RiskRepo(engagement_path).list_all():
        if r.created_at > since:
            changes.append(
                StateChange(
                    entity_type="risk",
                    entity_id=r.id,
                    change="created",
                    title=r.title,
                    timestamp=r.created_at,
                )
            )

    for q in OpenQuestionsRepo(engagement_path).list_all(status="answered"):
        if q.answered_at is not None and q.answered_at > since:
            changes.append(
                StateChange(
                    entity_type="question",
                    entity_id=q.id,
                    change="answered",
                    title=q.question,
                    timestamp=q.answered_at,
                )
            )

    return changes


def _state_changes_to_tasks(changes: list[StateChange]) -> list[CandidateTask]:
    """Convert ``StateChange`` rows into ``CandidateTask`` instances."""
    tasks: list[CandidateTask] = []
    for ch in changes:
        prefix = _STATE_CHANGE_TITLE_PREFIX[ch.entity_type]
        tasks.append(
            CandidateTask(
                task_type="state_change",
                description=f"{prefix}: {ch.title}",
                score=42.0,
                related_ids=[ch.entity_id],
                metadata={"change": ch.model_dump(mode="json")},
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


def gather_candidate_tasks(
    engagement_path: Path,
    *,
    stall_days: int = _STALL_DAYS,
    now: datetime | None = None,
    since: datetime | None = None,
) -> list[CandidateTask]:
    """Run all generators and return candidates sorted by score (highest first).

    *since* (D-033, optional) is the prior wake's ``ended_at`` timestamp.
    When supplied, ``find_recent_state_changes`` runs and emits a
    state-change CandidateTask per detected change.
    """
    candidates: list[CandidateTask] = []

    candidates.extend(find_stalled_questions(engagement_path, stall_days=stall_days, now=now))
    candidates.extend(find_insufficient_artifacts(engagement_path))
    candidates.extend(find_empty_areas(engagement_path))
    candidates.extend(find_agent_workitems(engagement_path))

    if since is not None:
        changes = find_recent_state_changes(engagement_path, since=since)
        candidates.extend(_state_changes_to_tasks(changes))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates
