"""Tests for the elicitation planner, stakeholder matching, and drafts."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.config.models import ProfileConfig
from praxis.core.elicitation import (
    ElicitationDraft,
    ElicitationMode,
    _parse_planner_response,
    plan_elicitations,
)
from praxis.core.stakeholder_match import (
    find_best_stakeholder,
    match_by_authority,
    match_by_expertise,
)
from praxis.core.sufficiency import (
    CandidateSource,
    InfoNeed,
    InfoNeedStatus,
    SufficiencyReport,
    SufficiencyVerdict,
)
from praxis.engagement import ContactChannel, StakeholderRepo
from praxis.engagement.models import Stakeholder
from praxis.errors import SufficiencyError
from praxis.storage.db import close_connection
from praxis.transport.base import Transport
from praxis.transport.models import (
    ChatRequest,
    ProbeResult,
    StreamChunk,
    Usage,
)

_PROFILE = ProfileConfig(name="test")


# ---------------------------------------------------------------------------
# Mock transport
# ---------------------------------------------------------------------------


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


def _make_report(
    *,
    stakeholder_id: str = "maria-l-x1",
    needs: list[InfoNeed] | None = None,
    verdict: SufficiencyVerdict = SufficiencyVerdict.INSUFFICIENT,
) -> SufficiencyReport:
    if needs is None:
        needs = [
            InfoNeed(
                need="What is the AP threshold?",
                status=InfoNeedStatus.UNKNOWN,
                blocker=True,
                candidate_sources=[
                    CandidateSource(
                        kind="stakeholder",
                        ref=stakeholder_id,
                        rationale="AP Manager",
                    )
                ],
            )
        ]
    return SufficiencyReport(
        artifact_kind="user-story",
        artifact_target="Invoice approval workflow",
        information_needs=needs,
        verdict=verdict,
        recommended_action="elicit",
        reasoning="Missing info",
        elicitation_targets=[stakeholder_id],
        generated_at="2024-01-01T00:00:00Z",
        by="agent",
    )


def _draft_response(
    stakeholder_id: str = "maria-l-x1",
    stakeholder_name: str = "Maria L.",
) -> list[dict[str, object]]:
    return [
        {
            "target_stakeholder_id": stakeholder_id,
            "target_stakeholder_name": stakeholder_name,
            "channel": "email",
            "mode": "direct_question",
            "priority": "high",
            "rationale": "Single direct question; AP Manager owns this.",
            "related_info_needs": ["What is the AP threshold?"],
            "blocks": [],
            "drafted_subject": "Question on invoice approval thresholds",
            "drafted_body": "Hi Maria, what is the AP threshold?",
            "expected_response_format": "free text",
            "followup_after_days": 3,
        }
    ]


# ---------------------------------------------------------------------------
# Stakeholder matching
# ---------------------------------------------------------------------------


class TestStakeholderMatching:
    def _make_stakeholder(
        self,
        *,
        sid: str = "s1",
        name: str = "Alice",
        expertise: list[str] | None = None,
        authority: list[str] | None = None,
    ) -> Stakeholder:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        return Stakeholder(
            id=sid,
            name=name,
            role="Analyst",
            expertise=expertise or [],
            decision_authority=authority or [],
            created_at=now,
            updated_at=now,
        )

    def test_match_by_expertise(self) -> None:
        s1 = self._make_stakeholder(sid="s1", expertise=["accounts payable", "invoicing"])
        s2 = self._make_stakeholder(sid="s2", expertise=["marketing"])
        matches = match_by_expertise("invoice approval accounts", [s1, s2])
        assert len(matches) >= 1
        assert matches[0].id == "s1"

    def test_match_by_authority(self) -> None:
        s1 = self._make_stakeholder(sid="s1", authority=["invoice approval threshold"])
        s2 = self._make_stakeholder(sid="s2", authority=["budget"])
        matches = match_by_authority("invoice approval workflow", [s1, s2])
        assert len(matches) >= 1
        assert matches[0].id == "s1"

    def test_find_best_preferred_id(self) -> None:
        s1 = self._make_stakeholder(sid="s1")
        s2 = self._make_stakeholder(sid="s2")
        result = find_best_stakeholder("anything", "anything", [s1, s2], preferred_ids=["s2"])
        assert result is not None
        assert result.id == "s2"

    def test_find_best_fallback_to_none(self) -> None:
        s1 = self._make_stakeholder(sid="s1", expertise=["unrelated"])
        result = find_best_stakeholder("invoice", "something", [s1])
        assert result is None


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


class TestPlannerParsing:
    def test_valid_array(self) -> None:
        data = _parse_planner_response('[{"key": "value"}]')
        assert len(data) == 1

    def test_markdown_fences(self) -> None:
        raw = '```json\n[{"key": "value"}]\n```'
        data = _parse_planner_response(raw)
        assert len(data) == 1

    def test_invalid_json(self) -> None:
        with pytest.raises(SufficiencyError, match="Failed to parse"):
            _parse_planner_response("not json")

    def test_non_array(self) -> None:
        with pytest.raises(SufficiencyError, match="not a JSON array"):
            _parse_planner_response('{"key": "value"}')


# ---------------------------------------------------------------------------
# Mode selection (via LLM response)
# ---------------------------------------------------------------------------


class TestModeSelection:
    def test_single_need_direct_question(self, eng: Path) -> None:
        s = StakeholderRepo(eng).add(name="Maria L.", role="AP Manager")

        transport = MockTransport()
        transport.queue_json(_draft_response(stakeholder_id=s.id, stakeholder_name="Maria L."))

        report = _make_report(stakeholder_id=s.id)
        drafts = plan_elicitations(report, transport=transport, engagement_path=eng)
        assert len(drafts) == 1
        assert drafts[0].mode == ElicitationMode.DIRECT_QUESTION

    def test_channel_from_stakeholder(self, eng: Path) -> None:
        s = StakeholderRepo(eng).add(
            name="Bob", role="Dev", contact_preference=ContactChannel.TEAMS
        )

        transport = MockTransport()
        transport.queue_json(
            [
                {
                    "target_stakeholder_id": s.id,
                    "target_stakeholder_name": "Bob",
                    "channel": "teams",
                    "mode": "direct_question",
                    "priority": "medium",
                    "rationale": "Simple question",
                    "related_info_needs": ["API endpoint details"],
                    "blocks": [],
                    "drafted_body": "Hi Bob, what are the API endpoints?",
                    "expected_response_format": "free text",
                }
            ]
        )

        report = _make_report(stakeholder_id=s.id)
        drafts = plan_elicitations(report, transport=transport, engagement_path=eng)
        assert len(drafts) == 1
        assert drafts[0].channel == ContactChannel.TEAMS


# ---------------------------------------------------------------------------
# Draft persistence
# ---------------------------------------------------------------------------


class TestDraftPersistence:
    def test_drafts_saved_to_disk(self, eng: Path) -> None:
        s = StakeholderRepo(eng).add(name="Maria L.", role="AP Manager")

        transport = MockTransport()
        transport.queue_json(_draft_response(stakeholder_id=s.id, stakeholder_name="Maria L."))

        report = _make_report(stakeholder_id=s.id)
        plan_elicitations(report, transport=transport, engagement_path=eng)

        drafts_dir = eng / ".praxis" / "state" / "elicitation-drafts"
        assert drafts_dir.is_dir()
        files = list(drafts_dir.glob("*.json"))
        assert len(files) == 1


# ---------------------------------------------------------------------------
# OpenQuestion creation
# ---------------------------------------------------------------------------


class TestOpenQuestionCreation:
    def test_questions_created(self, eng: Path) -> None:
        s = StakeholderRepo(eng).add(name="Maria L.", role="AP Manager")

        transport = MockTransport()
        transport.queue_json(_draft_response(stakeholder_id=s.id, stakeholder_name="Maria L."))

        report = _make_report(stakeholder_id=s.id)
        plan_elicitations(report, transport=transport, engagement_path=eng)

        from praxis.engagement import OpenQuestionsRepo

        questions = OpenQuestionsRepo(eng).load().questions
        assert any("threshold" in q.question.lower() for q in questions)
        assert s.id in questions[0].candidate_answerers

    def test_no_duplicate_questions(self, eng: Path) -> None:
        s = StakeholderRepo(eng).add(name="Maria L.", role="AP Manager")

        transport = MockTransport()
        # Run twice
        for _ in range(2):
            transport.queue_json(_draft_response(stakeholder_id=s.id, stakeholder_name="Maria L."))

        report = _make_report(stakeholder_id=s.id)
        plan_elicitations(report, transport=transport, engagement_path=eng)
        plan_elicitations(report, transport=transport, engagement_path=eng)

        from praxis.engagement import OpenQuestionsRepo

        questions = OpenQuestionsRepo(eng).load().questions
        threshold_qs = [q for q in questions if "threshold" in q.question.lower()]
        assert len(threshold_qs) == 1


# ---------------------------------------------------------------------------
# No gaps
# ---------------------------------------------------------------------------


class TestNoGaps:
    def test_no_drafts_when_sufficient(self, eng: Path) -> None:
        transport = MockTransport()
        report = _make_report(
            needs=[
                InfoNeed(
                    need="Actor identity",
                    status=InfoNeedStatus.KNOWN,
                    have="Finance Manager",
                    blocker=True,
                )
            ],
            verdict=SufficiencyVerdict.SUFFICIENT,
        )
        drafts = plan_elicitations(report, transport=transport, engagement_path=eng)
        assert drafts == []


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestElicitationModels:
    def test_mode_values(self) -> None:
        assert ElicitationMode.DIRECT_QUESTION == "direct_question"
        assert ElicitationMode.WORKSHOP == "workshop"
        assert ElicitationMode.MEETING_REQUEST == "meeting_request"

    def test_draft_round_trip(self) -> None:
        draft = ElicitationDraft(
            target_stakeholder_id="s1",
            target_stakeholder_name="Alice",
            channel=ContactChannel.EMAIL,
            mode=ElicitationMode.DIRECT_QUESTION,
            priority="high",
            rationale="Test",
            related_info_needs=["What is X?"],
            drafted_body="Hi, what is X?",
            expected_response_format="free text",
        )
        data = draft.model_dump(mode="json")
        restored = ElicitationDraft.model_validate(data)
        assert restored.target_stakeholder_id == "s1"

    def test_unknown_stakeholder(self) -> None:
        draft = ElicitationDraft(
            target_stakeholder_id="UNKNOWN",
            target_stakeholder_name="Unknown — please identify",
            channel=ContactChannel.OTHER,
            mode=ElicitationMode.DIRECT_QUESTION,
            priority="medium",
            rationale="No matching stakeholder",
            related_info_needs=["Who handles X?"],
            drafted_body="Please identify who handles X.",
            expected_response_format="free text",
        )
        assert draft.target_stakeholder_id == "UNKNOWN"
