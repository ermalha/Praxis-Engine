"""Integration tests for Chunk 11 — Human Work-Queue."""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.engagement import ContactChannel, OpenQuestionsRepo, StakeholderRepo
from praxis.storage.db import close_connection
from praxis.workqueue import (
    WorkItemPriority,
    WorkItemStatus,
    WorkItemType,
    WorkQueueRepo,
    prioritize,
)


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


class TestFullWorkqueueFlow:
    def test_full_lifecycle(self, eng: Path) -> None:
        """Full flow: create → list → start → done → verify audit events."""
        # 1. Create stakeholder + open question
        stakeholder = StakeholderRepo(eng).add(
            name="Maria L.",
            role="AP Manager",
            contact_preference=ContactChannel.EMAIL,
        )

        oq = OpenQuestionsRepo(eng).open(
            question="What is the AP threshold?",
            why_it_matters="Needed for invoice approval workflow",
            candidate_answerers=[stakeholder.id],
        )

        # 2. Create SEND_MESSAGE work-item (simulating elicitation draft → work-item)
        repo = WorkQueueRepo(eng)
        item = repo.enqueue(
            type=WorkItemType.SEND_MESSAGE,
            assignee="human",
            title="Email Maria about AP threshold",
            description="Send the drafted email to Maria L.",
            priority=WorkItemPriority.HIGH,
            rationale="Needed for invoice approval story",
            related_question_ids=[oq.id],
            related_stakeholder_ids=[stakeholder.id],
        )

        # 3. List queue — item appears
        items = repo.list(assignee="human")
        assert len(items) == 1
        assert items[0].id == item.id

        # Prioritized view shows it
        ordered = prioritize(items)
        assert len(ordered) == 1

        # 4. Start the item
        repo.transition(item.id, WorkItemStatus.IN_PROGRESS)

        # 5. Complete with return data (the answer)
        done_item = repo.transition(
            item.id,
            WorkItemStatus.DONE,
            note="Email sent, Maria replied: threshold is 10k",
            return_payload={"answer": "The AP threshold is $10,000"},
        )

        assert done_item.status == WorkItemStatus.DONE
        assert done_item.completed_at is not None
        assert done_item.completion_note is not None

        # 6. Verify JSONL log has entries
        jsonl_path = eng / ".praxis" / "state" / "workqueue.jsonl"
        assert jsonl_path.exists()
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) >= 3  # created + transition + done


class TestElicitationDraftToWorkItem:
    def test_draft_converts_to_send_message(self, eng: Path) -> None:
        """Elicitation draft becomes a SEND_MESSAGE work-item."""
        repo = WorkQueueRepo(eng)

        draft_payload = {
            "target_stakeholder_id": "maria-123",
            "drafted_subject": "Question about AP thresholds",
            "drafted_body": "Hi Maria, what are the AP thresholds?",
            "channel": "email",
        }

        item = repo.enqueue(
            type=WorkItemType.SEND_MESSAGE,
            assignee="human",
            title="Send: Question about AP thresholds",
            description="Send email to Maria L.",
            priority=WorkItemPriority.HIGH,
            payload=draft_payload,
            rationale="Elicitation draft from sufficiency gate",
        )

        assert item.type == WorkItemType.SEND_MESSAGE
        assert item.payload["drafted_subject"] == "Question about AP thresholds"


class TestAgentWorkItems:
    def test_agent_items_separate(self, eng: Path) -> None:
        repo = WorkQueueRepo(eng)

        repo.enqueue(
            type=WorkItemType.SEND_MESSAGE,
            assignee="human",
            title="Human task",
            description="",
            rationale="",
        )
        repo.enqueue(
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="agent",
            title="Agent task",
            description="",
            rationale="",
        )

        human = repo.list(assignee="human")
        agent = repo.list(assignee="agent")

        assert len(human) == 1
        assert len(agent) == 1
        assert human[0].assignee == "human"
        assert agent[0].assignee == "agent"
