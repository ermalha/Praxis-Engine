"""Integration tests for wake-cycle deduplication (D-032).

Closes RW-011: each wake cycle blindly created new work items, so after
three wakes against the same engagement state six identical
"Re-evaluate: spec" items piled up in the queue.

New behavior: `WorkQueueRepo.enqueue_deduped(dedup_key=..., ...)` checks
for an existing OPEN (queued/in_progress) item with the same key and
returns it instead of creating a duplicate. Wake's `_handle_*` methods
now route through `enqueue_deduped` with a stable per-task key.
"""

from __future__ import annotations

import json
from pathlib import Path

from praxis.config.engagement import init_engagement
from praxis.config.loader import load_engagement_config
from praxis.config.models import ModelConfig, ProfileConfig, Provider
from praxis.core.orchestrator import Orchestrator
from praxis.core.wake.models import WakeTrigger
from praxis.workqueue.models import WorkItemPriority, WorkItemStatus, WorkItemType
from praxis.workqueue.repo import WorkQueueRepo


def _make_orchestrator(eng_path: Path) -> Orchestrator:
    """Build an Orchestrator with a stub profile (no real LLM calls)."""
    eng_config = load_engagement_config(eng_path)
    profile = ProfileConfig(
        name="test",
        model_aliases={
            "default": ModelConfig(
                provider=Provider.OPENAI,
                model="gpt-test",
                api_key_env="OPENAI_API_KEY",
            )
        },
        default_model_alias="default",
    )
    return Orchestrator(
        agent=None,  # type: ignore[arg-type]
        profile=profile,
        engagement=eng_config,
        engagement_path=eng_path,
    )


def _write_insufficient_report(eng_path: Path, name: str = "report-1") -> Path:
    """Persist a sufficiency report with verdict=insufficient."""
    reports_dir = eng_path / ".praxis" / "state" / "sufficiency-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{name}.json"
    report_path.write_text(
        json.dumps(
            {
                "verdict": "insufficient",
                "artifact_kind": "spec",
                "artifact_target": "MVP functional requirements",
            }
        )
    )
    return report_path


class TestEnqueueDeduped:
    """Repo-level tests for `enqueue_deduped`."""

    def test_returns_existing_on_dedup_hit(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        repo = WorkQueueRepo(tmp_engagement)

        item1, created1 = repo.enqueue_deduped(
            dedup_key="empty:risks",
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="agent",
            title="Identify risks",
            description="x",
            priority=WorkItemPriority.MEDIUM,
        )
        item2, created2 = repo.enqueue_deduped(
            dedup_key="empty:risks",
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="agent",
            title="Identify risks",
            description="x",
            priority=WorkItemPriority.MEDIUM,
        )

        assert created1 is True
        assert created2 is False
        assert item1.id == item2.id
        # Only ONE item exists in the queue.
        all_items = repo.list(limit=100)
        assert len(all_items) == 1

    def test_creates_new_after_done(self, tmp_engagement: Path) -> None:
        """Dedup ignores items in terminal status — closing one lets a fresh
        one be created with the same key."""
        init_engagement(tmp_engagement, "Test")
        repo = WorkQueueRepo(tmp_engagement)

        item1, created1 = repo.enqueue_deduped(
            dedup_key="empty:risks",
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="agent",
            title="Identify risks",
            description="x",
        )
        assert created1 is True

        # Close the first item.
        repo.transition(item1.id, WorkItemStatus.IN_PROGRESS)
        repo.transition(item1.id, WorkItemStatus.DONE, note="handled")

        item2, created2 = repo.enqueue_deduped(
            dedup_key="empty:risks",
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="agent",
            title="Identify risks",
            description="x",
        )
        assert created2 is True
        assert item2.id != item1.id


class TestWakeIdempotency:
    """End-to-end: wake cycle doesn't pile up duplicates."""

    def test_wake_twice_same_state_no_duplicates(self, tmp_engagement: Path) -> None:
        """RW-011 regression: two wakes against an unchanged engagement state
        produce one work item, not two."""
        init_engagement(tmp_engagement, "Test")
        _write_insufficient_report(tmp_engagement)
        orch = _make_orchestrator(tmp_engagement)

        report1 = orch.wake_once(trigger=WakeTrigger.MANUAL)
        report2 = orch.wake_once(trigger=WakeTrigger.MANUAL)

        # First wake creates items for the insufficient report + empty-areas.
        assert len(report1.workitems_created) >= 1
        # Second wake creates NOTHING new — everything is already enqueued.
        assert report2.workitems_created == []

        # Verify only one "Re-evaluate" item exists.
        repo = WorkQueueRepo(tmp_engagement)
        all_items = repo.list(limit=100)
        review_items = [i for i in all_items if i.type == WorkItemType.REVIEW_ARTIFACT]
        assert len(review_items) == 1

    def test_wake_after_commit_recreates(self, tmp_engagement: Path) -> None:
        """Once the agent item is closed, a fresh wake produces a new one."""
        init_engagement(tmp_engagement, "Test")
        _write_insufficient_report(tmp_engagement)
        orch = _make_orchestrator(tmp_engagement)
        repo = WorkQueueRepo(tmp_engagement)

        report1 = orch.wake_once(trigger=WakeTrigger.MANUAL)
        review_id = next(
            i for i in repo.list(limit=100) if i.type == WorkItemType.REVIEW_ARTIFACT
        ).id
        assert review_id in report1.workitems_created

        # Close the review item.
        repo.transition(review_id, WorkItemStatus.IN_PROGRESS)
        repo.transition(review_id, WorkItemStatus.DONE, note="re-checked")

        report3 = orch.wake_once(trigger=WakeTrigger.MANUAL)
        # A new review item should have been created.
        new_review_items = [
            i
            for i in repo.list(limit=100)
            if i.type == WorkItemType.REVIEW_ARTIFACT and i.id != review_id
        ]
        assert len(new_review_items) == 1
        assert new_review_items[0].id in report3.workitems_created
