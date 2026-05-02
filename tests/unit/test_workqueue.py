"""Tests for work-queue: models, state machine, scoring, repo."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.errors import WorkqueueError
from praxis.storage.db import close_connection
from praxis.workqueue import (
    WorkItem,
    WorkItemPriority,
    WorkItemStatus,
    WorkItemType,
    WorkQueueRepo,
    is_valid_transition,
    prioritize,
    score_item,
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


def _make_item(
    *,
    status: WorkItemStatus = WorkItemStatus.QUEUED,
    priority: WorkItemPriority = WorkItemPriority.MEDIUM,
    blocks: list[str] | None = None,
    deadline: datetime | None = None,
    created_at: datetime | None = None,
) -> WorkItem:
    now = created_at or datetime.now(UTC)
    return WorkItem(
        id="wi-test123",
        type=WorkItemType.SEND_MESSAGE,
        assignee="human",
        status=status,
        priority=priority,
        title="Test item",
        description="Test description",
        rationale="Testing",
        blocks=blocks or [],
        created_at=now,
        updated_at=now,
        deadline=deadline,
    )


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


class TestStateMachine:
    def test_valid_queued_to_in_progress(self) -> None:
        assert is_valid_transition(WorkItemStatus.QUEUED, WorkItemStatus.IN_PROGRESS)

    def test_valid_in_progress_to_done(self) -> None:
        assert is_valid_transition(WorkItemStatus.IN_PROGRESS, WorkItemStatus.DONE)

    def test_valid_queued_to_rejected(self) -> None:
        assert is_valid_transition(WorkItemStatus.QUEUED, WorkItemStatus.REJECTED)

    def test_valid_queued_to_deferred(self) -> None:
        assert is_valid_transition(WorkItemStatus.QUEUED, WorkItemStatus.DEFERRED)

    def test_valid_deferred_to_queued(self) -> None:
        assert is_valid_transition(WorkItemStatus.DEFERRED, WorkItemStatus.QUEUED)

    def test_valid_blocked_to_in_progress(self) -> None:
        assert is_valid_transition(WorkItemStatus.BLOCKED, WorkItemStatus.IN_PROGRESS)

    def test_valid_any_to_superseded(self) -> None:
        for status in WorkItemStatus:
            if status != WorkItemStatus.SUPERSEDED:
                assert is_valid_transition(status, WorkItemStatus.SUPERSEDED)

    def test_invalid_done_to_queued(self) -> None:
        assert not is_valid_transition(WorkItemStatus.DONE, WorkItemStatus.QUEUED)

    def test_invalid_rejected_to_in_progress(self) -> None:
        assert not is_valid_transition(WorkItemStatus.REJECTED, WorkItemStatus.IN_PROGRESS)

    def test_invalid_queued_to_done(self) -> None:
        assert not is_valid_transition(WorkItemStatus.QUEUED, WorkItemStatus.DONE)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    def test_critical_scores_higher(self) -> None:
        critical = _make_item(priority=WorkItemPriority.CRITICAL)
        low = _make_item(priority=WorkItemPriority.LOW)
        assert score_item(critical) > score_item(low)

    def test_deadline_urgency(self) -> None:
        now = datetime.now(UTC)
        urgent = _make_item(deadline=now + timedelta(days=1))
        relaxed = _make_item(deadline=now + timedelta(days=30))
        assert score_item(urgent, now=now) > score_item(relaxed, now=now)

    def test_overdue_bonus(self) -> None:
        now = datetime.now(UTC)
        overdue = _make_item(deadline=now - timedelta(days=1))
        future = _make_item(deadline=now + timedelta(days=7))
        assert score_item(overdue, now=now) > score_item(future, now=now)

    def test_blocking_count(self) -> None:
        blocker = _make_item(blocks=["a", "b", "c"])
        non_blocker = _make_item()
        assert score_item(blocker) > score_item(non_blocker)

    def test_prioritize_orders(self) -> None:
        now = datetime.now(UTC)
        items = [
            _make_item(priority=WorkItemPriority.LOW),
            _make_item(priority=WorkItemPriority.CRITICAL),
            _make_item(priority=WorkItemPriority.HIGH),
        ]
        # Need different IDs for list
        for i, item in enumerate(items):
            items[i] = item.model_copy(update={"id": f"wi-{i}"})

        ordered = prioritize(items, now=now)
        assert ordered[0].priority == WorkItemPriority.CRITICAL
        assert ordered[-1].priority == WorkItemPriority.LOW


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class TestWorkQueueRepo:
    def test_enqueue_and_get(self, eng: Path) -> None:
        repo = WorkQueueRepo(eng)
        item = repo.enqueue(
            type=WorkItemType.SEND_MESSAGE,
            assignee="human",
            title="Send email to Maria",
            description="Ask about thresholds",
            priority=WorkItemPriority.HIGH,
            rationale="Missing AP info",
        )

        assert item.id.startswith("wi-")
        assert item.status == WorkItemStatus.QUEUED

        found = repo.get(item.id)
        assert found is not None
        assert found.title == "Send email to Maria"

    def test_list_filter(self, eng: Path) -> None:
        repo = WorkQueueRepo(eng)
        repo.enqueue(
            type=WorkItemType.SEND_MESSAGE,
            assignee="human",
            title="Item 1",
            description="",
            rationale="",
        )
        repo.enqueue(
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="agent",
            title="Item 2",
            description="",
            rationale="",
        )

        human_items = repo.list(assignee="human")
        assert len(human_items) == 1
        assert human_items[0].assignee == "human"

    def test_transition_valid(self, eng: Path) -> None:
        repo = WorkQueueRepo(eng)
        item = repo.enqueue(
            type=WorkItemType.ANSWER_QUESTION,
            assignee="human",
            title="Answer question",
            description="",
            rationale="",
        )

        updated = repo.transition(item.id, WorkItemStatus.IN_PROGRESS)
        assert updated.status == WorkItemStatus.IN_PROGRESS

        done = repo.transition(
            item.id,
            WorkItemStatus.DONE,
            note="Answered it",
            return_payload={"answer": "42"},
        )
        assert done.status == WorkItemStatus.DONE
        assert done.completion_note == "Answered it"
        assert done.completed_at is not None

    def test_transition_invalid(self, eng: Path) -> None:
        repo = WorkQueueRepo(eng)
        item = repo.enqueue(
            type=WorkItemType.SEND_MESSAGE,
            assignee="human",
            title="Test",
            description="",
            rationale="",
        )

        with pytest.raises(WorkqueueError, match="Invalid transition"):
            repo.transition(item.id, WorkItemStatus.DONE)

    def test_transition_not_found(self, eng: Path) -> None:
        repo = WorkQueueRepo(eng)
        with pytest.raises(WorkqueueError, match="not found"):
            repo.transition("wi-nonexistent", WorkItemStatus.IN_PROGRESS)

    def test_jsonl_log(self, eng: Path) -> None:
        repo = WorkQueueRepo(eng)
        repo.enqueue(
            type=WorkItemType.SEND_MESSAGE,
            assignee="human",
            title="Test",
            description="",
            rationale="",
        )

        jsonl_path = eng / ".praxis" / "state" / "workqueue.jsonl"
        assert jsonl_path.exists()
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) >= 1


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestModels:
    def test_work_item_type_values(self) -> None:
        assert WorkItemType.SEND_MESSAGE == "send_message"
        assert WorkItemType.AGENT_FOLLOW_UP == "agent_follow_up"

    def test_work_item_status_values(self) -> None:
        assert WorkItemStatus.QUEUED == "queued"
        assert WorkItemStatus.DONE == "done"
        assert WorkItemStatus.SUPERSEDED == "superseded"

    def test_work_item_round_trip(self) -> None:
        item = _make_item()
        data = item.model_dump(mode="json")
        restored = WorkItem.model_validate(data)
        assert restored.id == item.id
        assert restored.type == item.type

    def test_extra_forbid(self) -> None:
        with pytest.raises(Exception):  # noqa: B017, PT011
            WorkItem(
                id="test",
                type=WorkItemType.SEND_MESSAGE,
                assignee="human",
                status=WorkItemStatus.QUEUED,
                priority=WorkItemPriority.MEDIUM,
                title="Test",
                description="",
                rationale="",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                extra_field="bad",
            )
