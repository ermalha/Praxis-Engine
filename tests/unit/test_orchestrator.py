"""Tests for orchestrator: wake cycle, generators, daily plan, quiet hours."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.config.models import (
    EngagementConfig,
    ProfileConfig,
    WakeCycleConfig,
    WakeCycleMode,
)
from praxis.core.orchestrator import Orchestrator
from praxis.core.wake.daily_plan import generate_daily_plan
from praxis.core.wake.generators import (
    find_agent_workitems,
    find_empty_areas,
    find_insufficient_artifacts,
    find_stalled_questions,
    gather_candidate_tasks,
)
from praxis.core.wake.models import CandidateTask, WakeReport, WakeTrigger
from praxis.engagement.repos.questions import OpenQuestionsRepo
from praxis.engagement.repos.stakeholders import StakeholderRepo
from praxis.errors import OrchestratorError
from praxis.storage.db import close_connection
from praxis.workqueue import (
    WorkItemPriority,
    WorkItemStatus,
    WorkItemType,
    WorkQueueRepo,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def eng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    praxis_home = tmp_path / ".praxis"
    praxis_home.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRAXIS_HOME", str(praxis_home))
    monkeypatch.delenv("PRAXIS_PROFILE", raising=False)

    eng_dir = tmp_path / "test-engagement"
    eng_dir.mkdir()
    init_engagement(eng_dir, "Test Engagement")
    yield eng_dir
    close_connection(eng_dir / ".praxis" / "state" / "praxis.db")


def _make_orchestrator(
    eng: Path,
    *,
    quiet_hours: tuple[int, int] | None = None,
    mode: WakeCycleMode = WakeCycleMode.MANUAL,
) -> Orchestrator:
    profile = ProfileConfig(name="test")
    wake_cfg = WakeCycleConfig(mode=mode, quiet_hours=quiet_hours)
    engagement = EngagementConfig(name="Test", wake_cycle=wake_cfg)
    return Orchestrator(
        agent=None,  # type: ignore[arg-type]
        profile=profile,
        engagement=engagement,
        engagement_path=eng,
    )


# ---------------------------------------------------------------------------
# Wake models
# ---------------------------------------------------------------------------


class TestWakeModels:
    def test_wake_trigger_values(self) -> None:
        assert WakeTrigger.MANUAL == "manual"
        assert WakeTrigger.SCHEDULED == "scheduled"
        assert WakeTrigger.STARTUP == "startup"

    def test_candidate_task(self) -> None:
        task = CandidateTask(
            task_type="stalled_question",
            description="Follow up",
            score=50.0,
            related_ids=["q1"],
        )
        assert task.score == 50.0

    def test_wake_report_round_trip(self) -> None:
        now = datetime.now(UTC)
        report = WakeReport(
            started_at=now,
            ended_at=now,
            trigger=WakeTrigger.MANUAL,
            tasks_executed=["task1"],
        )
        data = report.model_dump(mode="json")
        restored = WakeReport.model_validate(data)
        assert restored.trigger == WakeTrigger.MANUAL


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


class TestGenerators:
    def test_stalled_questions_empty(self, eng: Path) -> None:
        tasks = find_stalled_questions(eng)
        assert tasks == []

    def test_stalled_question_detected(self, eng: Path) -> None:
        # Add a stakeholder first
        StakeholderRepo(eng).add(name="Maria", role="AP Lead")
        stakeholders = StakeholderRepo(eng).list_all()
        sid = stakeholders[0].id

        q_repo = OpenQuestionsRepo(eng)
        q = q_repo.open(
            "What's the AP threshold?",
            "Blocker for process map",
            candidate_answerers=[sid],
        )
        q_repo.mark_asked(q.id, asked_at=datetime.now(UTC) - timedelta(days=5))

        now = datetime.now(UTC)
        tasks = find_stalled_questions(eng, now=now)
        assert len(tasks) == 1
        assert tasks[0].task_type == "stalled_question"
        assert tasks[0].score > 50.0

    def test_stalled_question_not_stalled(self, eng: Path) -> None:
        """Questions asked recently should not be flagged."""
        q_repo = OpenQuestionsRepo(eng)
        q = q_repo.open("Recent question?", "Testing")
        q_repo.mark_asked(q.id, asked_at=datetime.now(UTC) - timedelta(hours=1))

        tasks = find_stalled_questions(eng)
        assert tasks == []

    def test_insufficient_artifacts(self, eng: Path) -> None:
        reports_dir = eng / ".praxis" / "state" / "sufficiency-reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "verdict": "insufficient",
            "artifact_kind": "user-story",
            "artifact_target": "Login flow",
        }
        (reports_dir / "test-report.json").write_text(json.dumps(report))

        tasks = find_insufficient_artifacts(eng)
        assert len(tasks) == 1
        assert tasks[0].task_type == "insufficient_artifact"

    def test_insufficient_skips_sufficient(self, eng: Path) -> None:
        reports_dir = eng / ".praxis" / "state" / "sufficiency-reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report = {"verdict": "sufficient", "artifact_kind": "spec", "artifact_target": "API"}
        (reports_dir / "ok.json").write_text(json.dumps(report))

        tasks = find_insufficient_artifacts(eng)
        assert tasks == []

    def test_empty_areas_no_stakeholders(self, eng: Path) -> None:
        tasks = find_empty_areas(eng)
        types = [t.task_type for t in tasks]
        assert "empty_stakeholders" in types

    def test_empty_areas_with_stakeholders(self, eng: Path) -> None:
        StakeholderRepo(eng).add(name="Alice", role="PM")
        tasks = find_empty_areas(eng)
        types = [t.task_type for t in tasks]
        assert "empty_stakeholders" not in types

    def test_agent_workitems(self, eng: Path) -> None:
        repo = WorkQueueRepo(eng)
        repo.enqueue(
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="agent",
            title="Follow up",
            description="Check status",
            rationale="Automated",
        )

        tasks = find_agent_workitems(eng)
        assert len(tasks) == 1
        assert tasks[0].task_type == "agent_workitem"

    def test_gather_sorts_by_score(self, eng: Path) -> None:
        """Composite gather returns candidates sorted by score (highest first)."""
        candidates = gather_candidate_tasks(eng)
        if len(candidates) > 1:
            assert candidates[0].score >= candidates[1].score


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class TestOrchestrator:
    def test_wake_once_empty_state(self, eng: Path) -> None:
        """Wake with nothing to do produces a report with no tasks executed."""
        # Add a stakeholder so empty_stakeholders doesn't fire
        StakeholderRepo(eng).add(name="Someone", role="PM")

        orch = _make_orchestrator(eng)
        report = orch.wake_once(trigger=WakeTrigger.MANUAL)

        assert isinstance(report, WakeReport)
        assert report.trigger == WakeTrigger.MANUAL

    def test_wake_stalled_question_creates_workitem(self, eng: Path) -> None:
        StakeholderRepo(eng).add(name="Maria L.", role="AP Lead")
        stakeholders = StakeholderRepo(eng).list_all()
        sid = stakeholders[0].id

        q_repo = OpenQuestionsRepo(eng)
        q = q_repo.open(
            "What's the AP threshold?",
            "Blocker",
            candidate_answerers=[sid],
        )
        q_repo.mark_asked(q.id, asked_at=datetime.now(UTC) - timedelta(days=5))

        orch = _make_orchestrator(eng)
        report = orch.wake_once(trigger=WakeTrigger.MANUAL)

        assert "stalled_question" in report.state_changes_observed
        wq = WorkQueueRepo(eng)
        items = wq.list(status=WorkItemStatus.QUEUED)
        followups = [i for i in items if i.type == WorkItemType.SEND_MESSAGE]
        assert len(followups) >= 1
        assert "follow" in followups[0].title.lower()

    def test_wake_empty_stakeholders_creates_workitem(self, eng: Path) -> None:
        orch = _make_orchestrator(eng)
        report = orch.wake_once(trigger=WakeTrigger.MANUAL)

        assert "empty_stakeholders" in report.state_changes_observed
        wq = WorkQueueRepo(eng)
        items = wq.list(status=WorkItemStatus.QUEUED)
        stakeholder_items = [i for i in items if "stakeholder" in i.title.lower()]
        assert len(stakeholder_items) >= 1

    def test_quiet_hours_defers(self, eng: Path) -> None:
        orch = _make_orchestrator(eng, quiet_hours=(22, 6))
        # Simulate a 3am wake
        now_3am = datetime.now(UTC).replace(hour=3, minute=0, second=0, microsecond=0)
        report = orch.wake_once(trigger=WakeTrigger.SCHEDULED, now=now_3am)

        assert report.notes == "Deferred: quiet hours"
        assert report.tasks_executed == []

    def test_quiet_hours_allows_outside(self, eng: Path) -> None:
        orch = _make_orchestrator(eng, quiet_hours=(22, 6))
        now_noon = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
        report = orch.wake_once(trigger=WakeTrigger.SCHEDULED, now=now_noon)

        assert report.notes is None  # Not deferred

    def test_budget_exceeded(self, eng: Path) -> None:
        """When token budget is 0, no tasks should execute."""
        orch = Orchestrator(
            agent=None,  # type: ignore[arg-type]
            profile=ProfileConfig(name="test"),
            engagement=EngagementConfig(name="Test"),
            engagement_path=eng,
            token_budget=0,
        )
        report = orch.wake_once(trigger=WakeTrigger.MANUAL)
        assert report.tasks_executed == []

    def test_dry_run_no_workitems(self, eng: Path) -> None:
        orch = _make_orchestrator(eng)

        wq_before = WorkQueueRepo(eng).list(limit=100)
        report = orch.wake_once(trigger=WakeTrigger.MANUAL, dry_run=True)
        wq_after = WorkQueueRepo(eng).list(limit=100)

        assert len(wq_before) == len(wq_after)
        # Dry-run tasks are prefixed
        for t in report.tasks_executed:
            assert t.startswith("[dry-run]")

    def test_run_forever_rejects_manual_mode(self, eng: Path) -> None:
        import threading

        orch = _make_orchestrator(eng, mode=WakeCycleMode.MANUAL)
        with pytest.raises(OrchestratorError, match="MANUAL"):
            orch.run_forever(cancel_event=threading.Event())

    def test_report_persisted(self, eng: Path) -> None:
        StakeholderRepo(eng).add(name="Someone", role="PM")
        orch = _make_orchestrator(eng)
        orch.wake_once(trigger=WakeTrigger.MANUAL)

        reports_dir = eng / ".praxis" / "state" / "wake-reports"
        assert reports_dir.exists()
        files = list(reports_dir.glob("*.json"))
        assert len(files) >= 1


# ---------------------------------------------------------------------------
# Daily plan
# ---------------------------------------------------------------------------


class TestDailyPlan:
    def test_generate_daily_plan(self, eng: Path) -> None:
        plan = generate_daily_plan(eng)
        assert plan.date == datetime.now(UTC).strftime("%Y-%m-%d")
        assert plan.summary

    def test_daily_plan_includes_workitems(self, eng: Path) -> None:
        repo = WorkQueueRepo(eng)
        repo.enqueue(
            type=WorkItemType.SEND_MESSAGE,
            assignee="human",
            title="Send critical email",
            description="Urgent",
            priority=WorkItemPriority.CRITICAL,
            rationale="Test",
        )

        plan = generate_daily_plan(eng)
        assert len(plan.top_workitems) >= 1
        assert "CRITICAL" in plan.top_workitems[0]

    def test_daily_plan_persists_md(self, eng: Path) -> None:
        plan = generate_daily_plan(eng)
        md_path = eng / ".praxis" / "artifacts" / "reports" / f"daily-plan-{plan.date}.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "Daily Plan" in content
