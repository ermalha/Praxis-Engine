"""Integration tests for Chunk 10 — Elicitation Planner."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.core.elicitation import ElicitationMode, plan_elicitations
from praxis.core.sufficiency import (
    CandidateSource,
    InfoNeed,
    InfoNeedStatus,
    SufficiencyReport,
    SufficiencyVerdict,
)
from praxis.engagement import ContactChannel, OpenQuestionsRepo, StakeholderRepo
from praxis.storage.db import close_connection
from praxis.transport.base import Transport
from praxis.transport.models import (
    ChatRequest,
    ProbeResult,
    StreamChunk,
    Usage,
)


class MockTransport(Transport):
    name = "mock"

    def __init__(self) -> None:
        self._queue: list[str] = []

    def queue_json(self, data: object) -> None:
        self._queue.append(json.dumps(data))

    def chat_stream(
        self,
        request: ChatRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Iterator[StreamChunk]:
        if not self._queue:
            msg = "No queued responses"
            raise RuntimeError(msg)
        text = self._queue.pop(0)
        yield StreamChunk(
            delta_text=text,
            finish_reason="stop",
            usage=Usage(prompt_tokens=10, completion_tokens=5),
        )

    def supports_tools(self) -> bool:
        return False

    def supports_caching(self) -> bool:
        return False

    def probe(self) -> ProbeResult:
        return ProbeResult(ok=True, provider="mock", model="mock")


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


class TestPlannerProducesTargetedDrafts:
    def test_full_flow(self, eng: Path) -> None:
        """Full flow: sufficiency report → elicitation drafts → open questions."""
        stakeholder = StakeholderRepo(eng).add(
            name="Maria L.",
            role="AP Manager",
            expertise=["accounts payable", "invoice approval"],
            decision_authority=["approval thresholds"],
            contact_preference=ContactChannel.EMAIL,
            contact_handle="maria.l@example.com",
        )

        report = SufficiencyReport(
            artifact_kind="user-story",
            artifact_target="Invoice approval workflow",
            information_needs=[
                InfoNeed(
                    need="What's the AP threshold?",
                    status=InfoNeedStatus.UNKNOWN,
                    blocker=True,
                    candidate_sources=[
                        CandidateSource(
                            kind="stakeholder",
                            ref=stakeholder.id,
                            rationale="AP Manager",
                        )
                    ],
                ),
            ],
            verdict=SufficiencyVerdict.INSUFFICIENT,
            recommended_action="elicit",
            reasoning="Threshold value missing",
            elicitation_targets=[stakeholder.id],
            generated_at="2024-01-01T00:00:00Z",
            by="agent",
        )

        transport = MockTransport()
        transport.queue_json(
            [
                {
                    "target_stakeholder_id": stakeholder.id,
                    "target_stakeholder_name": "Maria L.",
                    "channel": "email",
                    "mode": "direct_question",
                    "priority": "high",
                    "rationale": "Single direct question; AP Manager owns this.",
                    "related_info_needs": ["What's the AP threshold?"],
                    "blocks": [],
                    "drafted_subject": "Quick question on invoice approval thresholds",
                    "drafted_body": "Hi Maria, what are the AP thresholds?",
                    "expected_response_format": "free text",
                    "followup_after_days": 3,
                }
            ]
        )

        drafts = plan_elicitations(
            report,
            transport=transport,
            engagement_path=eng,
        )

        assert len(drafts) == 1
        d = drafts[0]
        assert d.target_stakeholder_id == stakeholder.id
        assert d.channel == ContactChannel.EMAIL
        assert d.mode == ElicitationMode.DIRECT_QUESTION

        # Verify drafts persisted
        drafts_dir = eng / ".praxis" / "state" / "elicitation-drafts"
        assert len(list(drafts_dir.glob("*.json"))) == 1

        # Verify open question created
        qs = OpenQuestionsRepo(eng).load().questions
        assert any("threshold" in q.question.lower() for q in qs)
        assert stakeholder.id in qs[0].candidate_answerers


class TestUnknownStakeholderFallback:
    def test_unknown_when_no_match(self, eng: Path) -> None:
        """When no stakeholder matches, draft targets UNKNOWN."""
        report = SufficiencyReport(
            artifact_kind="spec",
            artifact_target="Payment module",
            information_needs=[
                InfoNeed(
                    need="Integration protocol details",
                    status=InfoNeedStatus.UNKNOWN,
                    blocker=True,
                    candidate_sources=[],
                ),
            ],
            verdict=SufficiencyVerdict.INSUFFICIENT,
            recommended_action="elicit",
            reasoning="No source identified",
            generated_at="2024-01-01T00:00:00Z",
            by="agent",
        )

        transport = MockTransport()
        transport.queue_json(
            [
                {
                    "target_stakeholder_id": "UNKNOWN",
                    "target_stakeholder_name": "Unknown — please identify",
                    "channel": "other",
                    "mode": "direct_question",
                    "priority": "high",
                    "rationale": "No matching stakeholder identified.",
                    "related_info_needs": ["Integration protocol details"],
                    "blocks": [],
                    "drafted_body": "Please identify who handles integration protocols.",
                    "expected_response_format": "free text",
                }
            ]
        )

        drafts = plan_elicitations(
            report,
            transport=transport,
            engagement_path=eng,
        )

        assert len(drafts) == 1
        assert drafts[0].target_stakeholder_id == "UNKNOWN"
