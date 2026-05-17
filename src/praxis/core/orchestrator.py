"""The Praxis Orchestrator — wake-cycle driven, agent-led engagement management."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import structlog

from praxis.audit import emit
from praxis.config.models import EngagementConfig, ProfileConfig, WakeCycleMode
from praxis.core.agent import Agent
from praxis.errors import OrchestratorError
from praxis.workqueue import (
    WorkItemPriority,
    WorkItemStatus,
    WorkItemType,
    WorkQueueRepo,
)

from .wake.generators import gather_candidate_tasks
from .wake.models import CandidateTask, WakeReport, WakeTrigger

logger = structlog.get_logger()

_DEFAULT_TOP_K = 3
_DEFAULT_TOKEN_BUDGET = 50_000


class Orchestrator:
    """Drives the Praxis wake-cycle.

    ``wake_once`` executes a single iteration.  ``run_forever`` schedules
    repeated wakes per the engagement's ``WakeCycleConfig``.
    """

    def __init__(
        self,
        agent: Agent,
        profile: ProfileConfig,
        engagement: EngagementConfig,
        engagement_path: Path,
        *,
        top_k: int = _DEFAULT_TOP_K,
        token_budget: int = _DEFAULT_TOKEN_BUDGET,
    ) -> None:
        self._agent = agent
        self._profile = profile
        self._engagement = engagement
        self._engagement_path = engagement_path
        self._top_k = top_k
        self._token_budget = token_budget

    @property
    def engagement_path(self) -> Path:
        return self._engagement_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def wake_once(
        self,
        *,
        trigger: WakeTrigger,
        dry_run: bool = False,
        now: datetime | None = None,
    ) -> WakeReport:
        """Execute a single wake cycle."""
        now = now or datetime.now(UTC)
        started_at = now

        # Check quiet hours
        if self._in_quiet_hours(now):
            report = WakeReport(
                started_at=started_at,
                ended_at=datetime.now(UTC),
                trigger=trigger,
                notes="Deferred: quiet hours",
            )
            self._persist_report(report)
            emit(
                "wake.deferred",
                component="orchestrator",
                engagement_path=self._engagement_path,
                reason="quiet_hours",
            )
            return report

        # 1. Gather candidate tasks
        candidates = gather_candidate_tasks(self._engagement_path, now=now)
        tasks_considered = [c.description for c in candidates]
        state_changes = [c.task_type for c in candidates]

        # 2. Pick top K
        selected = candidates[: self._top_k]

        # 3. Execute
        tasks_executed: list[str] = []
        workitems_created: list[str] = []
        tokens_used = 0

        for task in selected:
            if tokens_used >= self._token_budget:
                emit(
                    "wake.budget_exceeded",
                    component="orchestrator",
                    engagement_path=self._engagement_path,
                    tokens_used=tokens_used,
                    budget=self._token_budget,
                )
                break

            if dry_run:
                tasks_executed.append(f"[dry-run] {task.description}")
                continue

            created_ids = self._execute_task(task)
            tasks_executed.append(task.description)
            workitems_created.extend(created_ids)

        ended_at = datetime.now(UTC)
        report = WakeReport(
            started_at=started_at,
            ended_at=ended_at,
            trigger=trigger,
            state_changes_observed=state_changes,
            tasks_considered=tasks_considered,
            tasks_executed=tasks_executed,
            workitems_created=workitems_created,
            tokens_used=tokens_used,
        )

        if not dry_run:
            self._persist_report(report)

        emit(
            "wake.completed",
            component="orchestrator",
            engagement_path=self._engagement_path,
            trigger=trigger.value,
            tasks_executed=len(tasks_executed),
            workitems_created=len(workitems_created),
        )

        return report

    def run_forever(self, *, cancel_event: threading.Event) -> None:
        """Run the orchestrator loop until *cancel_event* is set."""
        mode = self._engagement.wake_cycle.mode
        interval = self._engagement.wake_cycle.interval_minutes * 60

        if mode == WakeCycleMode.MANUAL:
            raise OrchestratorError(
                "Cannot run_forever in MANUAL mode; use SCHEDULED or MIXED",
                mode=mode.value,
            )

        # Startup wake
        self.wake_once(trigger=WakeTrigger.STARTUP)

        while not cancel_event.is_set():
            cancel_event.wait(timeout=interval)
            if cancel_event.is_set():
                break
            self.wake_once(trigger=WakeTrigger.SCHEDULED)

        logger.info("orchestrator.stopped", engagement=self._engagement.name)

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _execute_task(self, task: CandidateTask) -> list[str]:
        """Execute a single candidate task.  Returns created work-item IDs."""
        handler = _TASK_HANDLERS.get(task.task_type)
        if handler is None:
            logger.warning("orchestrator.unknown_task_type", task_type=task.task_type)
            return []
        return handler(self, task)

    def _handle_stalled_question(self, task: CandidateTask) -> list[str]:
        """Create a follow-up work-item for a stalled question."""
        qid = str(task.metadata.get("question_id", ""))
        repo = WorkQueueRepo(self._engagement_path)
        item, was_created = repo.enqueue_deduped(
            dedup_key=f"stalled_question:{qid}",
            type=WorkItemType.SEND_MESSAGE,
            assignee="human",
            title=f"Follow up on stalled question ({qid})",
            description=task.description,
            priority=WorkItemPriority.HIGH,
            rationale=(
                f"Question asked {task.metadata.get('days_stalled', '?')} days ago without answer"
            ),
            related_question_ids=[qid] if qid else [],
        )
        return [item.id] if was_created else []

    def _handle_insufficient_artifact(self, task: CandidateTask) -> list[str]:
        """Create a work-item to re-evaluate an insufficient artifact."""
        report_file = str(
            task.metadata.get("report_file") or task.metadata.get("artifact_target") or "unknown"
        )
        repo = WorkQueueRepo(self._engagement_path)
        item, was_created = repo.enqueue_deduped(
            dedup_key=f"insufficient:{report_file}",
            type=WorkItemType.REVIEW_ARTIFACT,
            assignee="agent",
            title=f"Re-evaluate: {task.metadata.get('artifact_kind', 'artifact')}",
            description=task.description,
            priority=WorkItemPriority.MEDIUM,
            rationale="Previous sufficiency check returned INSUFFICIENT",
        )
        return [item.id] if was_created else []

    def _handle_empty_stakeholders(self, _task: CandidateTask) -> list[str]:
        """Create an elicitation work-item for missing stakeholders."""
        repo = WorkQueueRepo(self._engagement_path)
        item, was_created = repo.enqueue_deduped(
            dedup_key="empty:stakeholders",
            type=WorkItemType.CONDUCT_INTERVIEW,
            assignee="human",
            title="Identify stakeholders for the engagement",
            description="No stakeholders identified yet. Start by identifying key stakeholders.",
            priority=WorkItemPriority.HIGH,
            rationale="Engagement has no stakeholders registered",
        )
        return [item.id] if was_created else []

    def _handle_empty_risks(self, _task: CandidateTask) -> list[str]:
        """Create a work-item for missing risk identification."""
        repo = WorkQueueRepo(self._engagement_path)
        item, was_created = repo.enqueue_deduped(
            dedup_key="empty:risks",
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="agent",
            title="Identify risks for the engagement",
            description="No risks have been registered yet. Propose initial risk identification.",
            priority=WorkItemPriority.MEDIUM,
            rationale="Engagement has no risks registered",
        )
        return [item.id] if was_created else []

    def _handle_agent_workitem(self, task: CandidateTask) -> list[str]:
        """Transition an agent work-item to in-progress."""
        wid = str(task.metadata.get("workitem_id", ""))
        if not wid:
            return []
        repo = WorkQueueRepo(self._engagement_path)
        repo.transition(wid, WorkItemStatus.IN_PROGRESS)
        return []

    # ------------------------------------------------------------------
    # Quiet hours
    # ------------------------------------------------------------------

    def _in_quiet_hours(self, now: datetime) -> bool:
        """Check if *now* falls within configured quiet hours."""
        qh = self._engagement.wake_cycle.quiet_hours
        if qh is None:
            return False
        start_hour, end_hour = qh
        hour = now.hour
        if start_hour < end_hour:
            return start_hour <= hour < end_hour
        # Wraps midnight, e.g. (23, 7)
        return hour >= start_hour or hour < end_hour

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_report(self, report: WakeReport) -> None:
        """Save a wake report to disk."""
        reports_dir = self._engagement_path / ".praxis" / "state" / "wake-reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        ts = report.started_at.strftime("%Y%m%dT%H%M%S")
        path = reports_dir / f"{ts}.json"
        path.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )


# Handler dispatch table — maps task_type to unbound method
_TASK_HANDLERS: dict[
    str,
    Callable[[Orchestrator, CandidateTask], list[str]],
] = {
    "stalled_question": Orchestrator._handle_stalled_question,
    "insufficient_artifact": Orchestrator._handle_insufficient_artifact,
    "empty_stakeholders": Orchestrator._handle_empty_stakeholders,
    "empty_risks": Orchestrator._handle_empty_risks,
    "agent_workitem": Orchestrator._handle_agent_workitem,
}
