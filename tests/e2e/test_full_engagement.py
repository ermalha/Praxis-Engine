"""E2E test — simulate a week-long 'ACME AP Modernization' engagement.

Uses ``MockTransport`` (FIFO queued responses) — no real LLM calls.
This is the final gate before tagging v0.1.0.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import praxis.engagement  # noqa: F401  — registers engagement tools
import praxis.tools.agent_tools  # noqa: F401  — registers agent tools
import praxis.tools.builtin  # noqa: F401  — registers debug tools
from praxis.config.engagement import init_engagement
from praxis.config.loader import load_engagement_config, save_engagement_config
from praxis.config.models import ProfileConfig, WakeCycleConfig
from praxis.core.agent import Agent
from praxis.core.orchestrator import Orchestrator
from praxis.core.wake.generators import gather_candidate_tasks
from praxis.core.wake.models import WakeTrigger
from praxis.engagement import (
    GlossaryRepo,
    OpenQuestionsRepo,
    RiskRepo,
    StakeholderRepo,
    SystemLandscapeRepo,
)
from praxis.storage.db import close_connection
from praxis.tools.models import ApprovalDecision
from praxis.tools.registry import default_registry
from praxis.transport.base import Transport
from praxis.transport.models import (
    ChatRequest,
    ChatResponse,
    ProbeResult,
    StreamChunk,
    ToolCall,
    ToolCallDelta,
    Usage,
)
from praxis.workqueue import (
    WorkItemPriority,
    WorkItemStatus,
    WorkItemType,
    WorkQueueRepo,
)

# ---------------------------------------------------------------------------
# Mock transport (same pattern as tests/unit/test_agent.py)
# ---------------------------------------------------------------------------


class MockTransport(Transport):
    """Test transport that returns queued responses."""

    name = "mock"

    def __init__(self) -> None:
        self._queue: list[ChatResponse] = []

    def queue_response(
        self,
        text: str = "",
        tool_calls: list[ToolCall] | None = None,
        finish_reason: str | None = None,
    ) -> None:
        if finish_reason is None:
            finish_reason = "tool_use" if tool_calls else "stop"
        self._queue.append(
            ChatResponse(
                content=text,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=Usage(prompt_tokens=10, completion_tokens=5),
            )
        )

    def chat_stream(
        self,
        request: ChatRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Iterator[StreamChunk]:
        if not self._queue:
            msg = "No queued responses"
            raise RuntimeError(msg)
        resp = self._queue.pop(0)
        yield StreamChunk(
            delta_text=resp.content if resp.content else None,
            finish_reason=resp.finish_reason,
            usage=resp.usage,
        )
        if resp.tool_calls:
            for i, tc in enumerate(resp.tool_calls):
                yield StreamChunk(
                    tool_call_delta=ToolCallDelta(
                        index=i,
                        id=tc.id,
                        name=tc.name,
                        arguments_delta=tc.arguments_json,
                    )
                )

    def supports_tools(self) -> bool:
        return True

    def supports_caching(self) -> bool:
        return False

    def probe(self) -> ProbeResult:
        return ProbeResult(ok=True, provider="mock", model="mock")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROFILE = ProfileConfig(name="test-analyst")


def _always_approve(_spec: object, _args: object) -> ApprovalDecision:
    return ApprovalDecision.APPROVE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def eng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Initialized engagement with sandboxed HOME."""
    praxis_home = tmp_path / ".praxis"
    praxis_home.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRAXIS_HOME", str(praxis_home))
    monkeypatch.delenv("PRAXIS_PROFILE", raising=False)

    eng_dir = tmp_path / "acme-ap-modernization"
    eng_dir.mkdir()
    init_engagement(eng_dir, "ACME AP Modernization")
    yield eng_dir
    close_connection(eng_dir / ".praxis" / "state" / "praxis.db")


@pytest.fixture()
def transport() -> MockTransport:
    return MockTransport()


@pytest.fixture()
def agent(eng: Path, transport: MockTransport) -> Iterator[Agent]:
    """Agent wired for E2E testing."""
    a = Agent(
        profile=_PROFILE,
        engagement_path=eng,
        transport=transport,
        tool_registry=default_registry,
        approval_callback=_always_approve,
        max_tool_iterations=10,
        enabled_toolsets={"engagement", "agent", "debug", "meta"},
    )
    a.start_session()
    yield a
    a.end_session(summary="E2E test session")


# ===================================================================
# Day 1 — Bootstrap
# ===================================================================


class TestDay1Bootstrap:
    """Orchestrator wake detects an empty engagement; agent populates it."""

    def test_initial_wake_detects_empty_engagement(self, eng: Path) -> None:
        """gather_candidate_tasks should flag empty_stakeholders on a fresh engagement."""
        candidates = gather_candidate_tasks(eng)
        task_types = [c.task_type for c in candidates]
        assert "empty_stakeholders" in task_types

    def test_agent_adds_stakeholders_via_tool(
        self, eng: Path, transport: MockTransport, agent: Agent
    ) -> None:
        """Mock LLM calls stakeholder_add; verify the repo is updated."""
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="tc-sh1",
                    name="stakeholder_add",
                    arguments_json=json.dumps(
                        {
                            "name": "Jane Chen",
                            "role": "CFO",
                            "expertise": ["finance", "ap-processes"],
                            "decision_authority": ["budget-approval"],
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="Added stakeholder Jane Chen.")

        resp = agent.turn("Add key stakeholders for the ACME AP project")
        assert resp.tool_call_count == 1

        stakeholders = StakeholderRepo(eng).list_all()
        assert len(stakeholders) == 1
        assert stakeholders[0].name == "Jane Chen"
        assert stakeholders[0].role == "CFO"

    def test_agent_populates_glossary(
        self, eng: Path, transport: MockTransport, agent: Agent
    ) -> None:
        """Mock LLM calls glossary_add_term; verify the glossary."""
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="tc-gl1",
                    name="glossary_add_term",
                    arguments_json=json.dumps(
                        {
                            "term": "Three-way match",
                            "definition": (
                                "Verification that PO, receipt, and invoice agree before payment."
                            ),
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="Added glossary term.")

        resp = agent.turn("Define key AP terms")
        assert resp.tool_call_count == 1

        glossary = GlossaryRepo(eng).load()
        assert any(t.term == "Three-way match" for t in glossary.terms)


# ===================================================================
# Day 2 — Elicitation
# ===================================================================


class TestDay2Elicitation:
    """Agent opens questions and records answers."""

    def test_agent_opens_question_for_stakeholder(
        self, eng: Path, transport: MockTransport, agent: Agent
    ) -> None:
        """Pre-seed a stakeholder, then mock question_open."""
        # Pre-seed stakeholder so candidate_answerers reference is valid
        sh = StakeholderRepo(eng).add("Jane Chen", "CFO")

        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="tc-qo1",
                    name="question_open",
                    arguments_json=json.dumps(
                        {
                            "question": "What is the current invoice approval threshold?",
                            "why_it_matters": "Needed to model the approval workflow.",
                            "candidate_answerers": [sh.id],
                            "priority": "high",
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="Question opened.")

        resp = agent.turn("Ask about invoice thresholds")
        assert resp.tool_call_count == 1

        questions = OpenQuestionsRepo(eng).list_all()
        assert len(questions) == 1
        assert "invoice approval threshold" in questions[0].question

    def test_agent_records_answer(self, eng: Path, transport: MockTransport, agent: Agent) -> None:
        """Pre-seed stakeholder + question, then mock question_answer."""
        StakeholderRepo(eng).add("Jane Chen", "CFO")
        q = OpenQuestionsRepo(eng).open(
            "What is the current invoice approval threshold?",
            "Needed to model the approval workflow.",
        )

        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="tc-qa1",
                    name="question_answer",
                    arguments_json=json.dumps(
                        {
                            "question_id": q.id,
                            "answer": "$10,000 for department heads, $50,000 requires VP sign-off.",
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="Answer recorded.")

        resp = agent.turn("Record the answer about thresholds")
        assert resp.tool_call_count == 1

        updated = OpenQuestionsRepo(eng).get(q.id)
        assert updated is not None
        assert updated.status == "answered"
        assert "$10,000" in (updated.answer or "")


# ===================================================================
# Day 3 — Wake cycle detects staleness
# ===================================================================


class TestDay3Staleness:
    """Stalled questions trigger follow-up work items."""

    def test_stalled_question_triggers_followup(
        self, eng: Path, transport: MockTransport, agent: Agent
    ) -> None:
        """Mark a question asked 5 days ago, wake_once → stalled_question → SEND_MESSAGE."""
        StakeholderRepo(eng).add("Jane Chen", "CFO")
        q = OpenQuestionsRepo(eng).open(
            "What are the current SLA targets for AP processing?",
            "Needed for baseline metrics.",
        )
        # Transition to 'asked' 5 days ago
        five_days_ago = datetime.now(UTC) - timedelta(days=5)
        OpenQuestionsRepo(eng).mark_asked(q.id, asked_at=five_days_ago)

        engagement_config = load_engagement_config(eng)
        orchestrator = Orchestrator(
            agent=agent,
            profile=_PROFILE,
            engagement=engagement_config,
            engagement_path=eng,
        )

        report = orchestrator.wake_once(trigger=WakeTrigger.MANUAL)
        assert len(report.workitems_created) >= 1

        # Verify work item was created
        repo = WorkQueueRepo(eng)
        items = repo.list(status=WorkItemStatus.QUEUED)
        follow_ups = [
            i for i in items if "stalled" in i.title.lower() or "follow" in i.title.lower()
        ]
        assert len(follow_ups) >= 1


# ===================================================================
# Day 4 — Risks & systems
# ===================================================================


class TestDay4RisksAndSystems:
    """Agent adds risks and systems to the engagement model."""

    def test_agent_adds_risk(self, eng: Path, transport: MockTransport, agent: Agent) -> None:
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="tc-r1",
                    name="risk_add",
                    arguments_json=json.dumps(
                        {
                            "title": "ERP upgrade delay",
                            "description": "SAP S/4HANA migration may slip past Q3.",
                            "likelihood": "medium",
                            "impact": "high",
                            "mitigation": "Parallel run with legacy system for 2 months.",
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="Risk added.")

        resp = agent.turn("Add ERP upgrade risk")
        assert resp.tool_call_count == 1

        risks = RiskRepo(eng).list_all()
        assert len(risks) == 1
        assert risks[0].title == "ERP upgrade delay"
        assert risks[0].likelihood == "medium"

    def test_agent_adds_system(self, eng: Path, transport: MockTransport, agent: Agent) -> None:
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="tc-s1",
                    name="system_add",
                    arguments_json=json.dumps(
                        {
                            "name": "SAP S/4HANA",
                            "kind": "erp",
                            "description": "Core ERP system for finance and procurement.",
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="System added.")

        resp = agent.turn("Register core systems")
        assert resp.tool_call_count == 1

        systems = SystemLandscapeRepo(eng).list_all()
        assert len(systems) == 1
        assert systems[0].name == "SAP S/4HANA"
        assert systems[0].kind == "erp"


# ===================================================================
# Day 5 — Work queue lifecycle
# ===================================================================


class TestDay5WorkQueue:
    """Full work-item lifecycle: QUEUED → IN_PROGRESS → DONE."""

    def test_work_item_full_lifecycle(self, eng: Path) -> None:
        repo = WorkQueueRepo(eng)
        item = repo.enqueue(
            type=WorkItemType.CONDUCT_INTERVIEW,
            assignee="human",
            title="Interview CFO about AP pain points",
            description="Conduct structured interview with Jane Chen.",
            priority=WorkItemPriority.HIGH,
            rationale="Key stakeholder, no data yet.",
        )
        assert item.status == WorkItemStatus.QUEUED

        # Transition: QUEUED → IN_PROGRESS
        item = repo.transition(item.id, WorkItemStatus.IN_PROGRESS)
        assert item.status == WorkItemStatus.IN_PROGRESS

        # Transition: IN_PROGRESS → DONE with return_payload
        item = repo.transition(
            item.id,
            WorkItemStatus.DONE,
            note="Interview complete, notes uploaded.",
            return_payload={"interview_notes_path": "artifacts/interviews/jane-chen.md"},
        )
        assert item.status == WorkItemStatus.DONE
        assert item.completed_at is not None
        assert item.return_payload is not None
        assert item.return_payload["interview_notes_path"] == "artifacts/interviews/jane-chen.md"


# ===================================================================
# Day 6 — Multi-turn & orchestrator
# ===================================================================


class TestDay6MultiTurnOrchestrator:
    """Chained tool calls, quiet hours, and dry-run."""

    def test_chained_tool_calls(self, eng: Path, transport: MockTransport, agent: Agent) -> None:
        """Two sequential tool calls in one conversation turn (3 queued responses)."""
        # First response: add a stakeholder
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="tc-chain1",
                    name="stakeholder_add",
                    arguments_json=json.dumps(
                        {
                            "name": "Bob Kim",
                            "role": "AP Manager",
                        }
                    ),
                )
            ]
        )
        # Second response: add a glossary term
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="tc-chain2",
                    name="glossary_add_term",
                    arguments_json=json.dumps(
                        {
                            "term": "P2P",
                            "definition": "Procure-to-Pay, the end-to-end purchasing cycle.",
                        }
                    ),
                )
            ]
        )
        # Third response: final text
        transport.queue_response(text="Added Bob Kim and P2P term.")

        resp = agent.turn("Add AP manager and define P2P")
        assert resp.tool_call_count == 2

        assert len(StakeholderRepo(eng).list_all()) == 1
        glossary = GlossaryRepo(eng).load()
        assert any(t.term == "P2P" for t in glossary.terms)

    def test_quiet_hours_defers_wake(
        self, eng: Path, transport: MockTransport, agent: Agent
    ) -> None:
        """Set quiet_hours=(22, 6), wake at 3am → deferred."""
        config = load_engagement_config(eng)
        config = config.model_copy(update={"wake_cycle": WakeCycleConfig(quiet_hours=(22, 6))})
        save_engagement_config(eng, config)

        orchestrator = Orchestrator(
            agent=agent,
            profile=_PROFILE,
            engagement=config,
            engagement_path=eng,
        )

        # 3am should be inside quiet hours (22–6)
        three_am = datetime(2025, 6, 15, 3, 0, 0, tzinfo=UTC)
        report = orchestrator.wake_once(trigger=WakeTrigger.MANUAL, now=three_am)
        assert "Deferred" in (report.notes or "")
        assert len(report.tasks_executed) == 0

    def test_dry_run_does_not_mutate(
        self, eng: Path, transport: MockTransport, agent: Agent
    ) -> None:
        """dry_run=True should not create work items."""
        config = load_engagement_config(eng)
        orchestrator = Orchestrator(
            agent=agent,
            profile=_PROFILE,
            engagement=config,
            engagement_path=eng,
        )

        # Count work items before
        before_count = len(WorkQueueRepo(eng).list())

        report = orchestrator.wake_once(trigger=WakeTrigger.MANUAL, dry_run=True)

        # All executed tasks should be prefixed with [dry-run]
        for task_desc in report.tasks_executed:
            assert task_desc.startswith("[dry-run]")

        # No new work items
        after_count = len(WorkQueueRepo(eng).list())
        assert after_count == before_count


# ===================================================================
# Day 7 — Full week scenario & guard rails
# ===================================================================


class TestDay7FullScenario:
    """End-to-end full week and iteration guard."""

    def test_full_week_scenario(self, eng: Path, transport: MockTransport, agent: Agent) -> None:
        """Single long test: the full engagement lifecycle in one go.

        1. Add stakeholder  2. Add glossary  3. Open question  4. Stale it
        5. Wake → follow-up  6. Answer question  7. Add risk
        8. Work item lifecycle  9. Verify final state
        """
        # --- Step 1: Add stakeholder ---
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="fw-sh",
                    name="stakeholder_add",
                    arguments_json=json.dumps(
                        {
                            "name": "Alice Park",
                            "role": "VP Finance",
                            "expertise": ["corporate-finance"],
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="Stakeholder added.")
        resp = agent.turn("Add VP Finance as stakeholder")
        assert resp.tool_call_count == 1
        stakeholders = StakeholderRepo(eng).list_all()
        assert len(stakeholders) == 1
        alice_id = stakeholders[0].id

        # --- Step 2: Add glossary term ---
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="fw-gl",
                    name="glossary_add_term",
                    arguments_json=json.dumps(
                        {
                            "term": "Invoice",
                            "definition": "A document requesting payment for goods or services.",
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="Term added.")
        resp = agent.turn("Define 'Invoice'")
        assert resp.tool_call_count == 1

        # --- Step 3: Open question ---
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="fw-qo",
                    name="question_open",
                    arguments_json=json.dumps(
                        {
                            "question": "What is the target cycle time for invoice processing?",
                            "why_it_matters": "Required for SLA definition.",
                            "candidate_answerers": [alice_id],
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="Question opened.")
        resp = agent.turn("Ask about cycle time targets")
        assert resp.tool_call_count == 1
        questions = OpenQuestionsRepo(eng).list_all()
        assert len(questions) == 1
        qid = questions[0].id

        # --- Step 4: Stale the question (simulate 5 days passing) ---
        five_days_ago = datetime.now(UTC) - timedelta(days=5)
        OpenQuestionsRepo(eng).mark_asked(qid, asked_at=five_days_ago)

        # --- Step 5: Wake cycle → follow-up work item ---
        config = load_engagement_config(eng)
        orchestrator = Orchestrator(
            agent=agent,
            profile=_PROFILE,
            engagement=config,
            engagement_path=eng,
        )
        report = orchestrator.wake_once(trigger=WakeTrigger.MANUAL)
        # Should have created at least one work item (stalled question follow-up)
        assert len(report.workitems_created) >= 1

        # --- Step 6: Answer the question ---
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="fw-qa",
                    name="question_answer",
                    arguments_json=json.dumps(
                        {
                            "question_id": qid,
                            "answer": "Target is 3 business days from receipt to payment.",
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="Answered.")
        resp = agent.turn("Record the cycle time answer")
        assert resp.tool_call_count == 1

        answered_q = OpenQuestionsRepo(eng).get(qid)
        assert answered_q is not None
        assert answered_q.status == "answered"

        # --- Step 7: Add risk ---
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="fw-rk",
                    name="risk_add",
                    arguments_json=json.dumps(
                        {
                            "title": "Vendor portal downtime",
                            "description": (
                                "External vendor portal may be unavailable during migration."
                            ),
                            "likelihood": "low",
                            "impact": "high",
                        }
                    ),
                )
            ]
        )
        transport.queue_response(text="Risk added.")
        resp = agent.turn("Add vendor portal risk")
        assert resp.tool_call_count == 1

        # --- Step 8: Work item lifecycle ---
        wq_repo = WorkQueueRepo(eng)
        item = wq_repo.enqueue(
            type=WorkItemType.SEND_MESSAGE,
            assignee="human",
            title="Notify AP team of new SLA targets",
            description="Share the 3-day cycle time target with the AP team.",
            priority=WorkItemPriority.MEDIUM,
            rationale="SLA target just confirmed by VP Finance.",
        )
        item = wq_repo.transition(item.id, WorkItemStatus.IN_PROGRESS)
        item = wq_repo.transition(
            item.id,
            WorkItemStatus.DONE,
            return_payload={"notification_sent": True},
        )
        assert item.status == WorkItemStatus.DONE

        # --- Step 9: Verify final engagement state ---
        final_stakeholders = StakeholderRepo(eng).list_all()
        assert len(final_stakeholders) >= 1

        final_glossary = GlossaryRepo(eng).load()
        assert len(final_glossary.terms) >= 1

        final_questions = OpenQuestionsRepo(eng).list_all()
        assert any(q.status == "answered" for q in final_questions)

        final_risks = RiskRepo(eng).list_all()
        assert len(final_risks) >= 1

        # Wake reports directory should have at least one report
        reports_dir = eng / ".praxis" / "state" / "wake-reports"
        assert reports_dir.exists()
        assert len(list(reports_dir.glob("*.json"))) >= 1

    def test_max_iterations_guard(self, eng: Path, transport: MockTransport) -> None:
        """Agent with max_tool_iterations=2, queue 5 tool responses → truncated."""
        # Create a dedicated agent with low iteration cap
        capped_agent = Agent(
            profile=_PROFILE,
            engagement_path=eng,
            transport=transport,
            tool_registry=default_registry,
            approval_callback=_always_approve,
            max_tool_iterations=2,
            enabled_toolsets={"engagement", "agent", "debug", "meta"},
        )
        capped_agent.start_session()

        # Queue 5 tool-call responses (more than the cap)
        for i in range(5):
            transport.queue_response(
                tool_calls=[
                    ToolCall(
                        id=f"tc-loop-{i}",
                        name="current_time",
                        arguments_json="{}",
                    )
                ]
            )

        resp = capped_agent.turn("Keep checking the time")
        assert resp.truncated is True
        capped_agent.end_session(summary="Iteration guard test")
