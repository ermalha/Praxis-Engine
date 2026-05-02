"""Tests for the sufficiency gate: models, templates, parsing, validation."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.config.models import ProfileConfig
from praxis.core.sufficiency import (
    InfoNeed,
    InfoNeedStatus,
    SufficiencyReport,
    SufficiencyVerdict,
    _parse_llm_response,
    _validate_cross_refs,
    run_sufficiency_gate,
)
from praxis.core.sufficiency_helpers import clear_cache, list_template_kinds, load_template
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
    """Transport that returns a queued JSON response."""

    name = "mock"

    def __init__(self) -> None:
        self._queue: list[str] = []

    def queue_json(self, data: dict[str, object]) -> None:
        self._queue.append(json.dumps(data))

    def queue_raw(self, text: str) -> None:
        self._queue.append(text)

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
    """Create an initialized engagement for testing."""
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


def _sufficient_response() -> dict[str, object]:
    return {
        "artifact_kind": "user-story",
        "artifact_target": "Invoice approval",
        "information_needs": [
            {
                "need": "Actor identity",
                "status": "known",
                "have": "Finance Manager",
                "missing": None,
                "blocker": True,
                "candidate_sources": [],
            },
            {
                "need": "Action goal",
                "status": "known",
                "have": "Approve invoices",
                "missing": None,
                "blocker": True,
                "candidate_sources": [],
            },
        ],
        "verdict": "sufficient",
        "recommended_action": "produce",
        "reasoning": "All critical info is available.",
        "elicitation_targets": [],
    }


def _insufficient_response(stakeholder_id: str = "maria-l-x1") -> dict[str, object]:
    return {
        "artifact_kind": "user-story",
        "artifact_target": "Invoice approval",
        "information_needs": [
            {
                "need": "Approval thresholds",
                "status": "unknown",
                "have": None,
                "missing": "Threshold values",
                "blocker": True,
                "candidate_sources": [
                    {
                        "kind": "stakeholder",
                        "ref": stakeholder_id,
                        "rationale": "AP Manager",
                    }
                ],
            }
        ],
        "verdict": "insufficient",
        "recommended_action": "elicit",
        "reasoning": "Threshold value missing",
        "elicitation_targets": [stakeholder_id],
    }


def _partial_response() -> dict[str, object]:
    return {
        "artifact_kind": "spec",
        "artifact_target": "Payment module",
        "information_needs": [
            {
                "need": "Scope boundaries",
                "status": "known",
                "have": "Payment processing",
                "missing": None,
                "blocker": True,
                "candidate_sources": [],
            },
            {
                "need": "Business rules",
                "status": "partial",
                "have": "Some rules defined",
                "missing": "Edge case rules",
                "blocker": False,
                "candidate_sources": [],
            },
        ],
        "verdict": "partial",
        "recommended_action": "produce_with_caveats",
        "reasoning": "Some info is partial but no blockers.",
    }


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------


class TestTemplateLoading:
    def setup_method(self) -> None:
        clear_cache()

    def test_load_known_template(self) -> None:
        needs = load_template("user-story")
        assert len(needs) >= 4
        assert any("Actor" in n["need"] for n in needs)

    def test_load_unknown_template(self) -> None:
        needs = load_template("unknown-kind")
        assert needs == []

    def test_list_template_kinds(self) -> None:
        kinds = list_template_kinds()
        assert "user-story" in kinds
        assert "spec" in kinds
        assert "decision-matrix" in kinds
        assert "process-model" in kinds
        assert "risk-register-entry" in kinds
        assert len(kinds) == 5

    def test_template_cache(self) -> None:
        needs1 = load_template("user-story")
        needs2 = load_template("user-story")
        assert needs1 is needs2  # Same object from cache


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


class TestJsonParsing:
    def test_valid_json(self) -> None:
        data = _parse_llm_response('{"verdict": "sufficient"}')
        assert data["verdict"] == "sufficient"

    def test_markdown_fences(self) -> None:
        raw = '```json\n{"verdict": "sufficient"}\n```'
        data = _parse_llm_response(raw)
        assert data["verdict"] == "sufficient"

    def test_invalid_json(self) -> None:
        with pytest.raises(SufficiencyError, match="Failed to parse"):
            _parse_llm_response("not json at all")

    def test_non_object_json(self) -> None:
        with pytest.raises(SufficiencyError, match="not a JSON object"):
            _parse_llm_response("[1, 2, 3]")


# ---------------------------------------------------------------------------
# Cross-reference validation
# ---------------------------------------------------------------------------


class TestCrossRefValidation:
    def test_no_refs_passes(self, eng: Path) -> None:
        report = SufficiencyReport.model_validate(
            {**_sufficient_response(), "generated_at": "2024-01-01T00:00:00Z", "by": "agent"}
        )
        # Should not raise
        _validate_cross_refs(report, eng)

    def test_valid_stakeholder_ref(self, eng: Path) -> None:
        from praxis.engagement import StakeholderRepo

        s = StakeholderRepo(eng).add(name="Maria L.", role="AP Manager")
        sid = s.id

        data = _insufficient_response(stakeholder_id=sid)
        report = SufficiencyReport.model_validate(
            {**data, "generated_at": "2024-01-01T00:00:00Z", "by": "agent"}
        )
        # Should not raise
        _validate_cross_refs(report, eng)

    def test_invalid_stakeholder_ref(self, eng: Path) -> None:
        report = SufficiencyReport.model_validate(
            {
                **_insufficient_response(stakeholder_id="nonexistent-id"),
                "generated_at": "2024-01-01T00:00:00Z",
                "by": "agent",
            }
        )
        with pytest.raises(SufficiencyError, match="not found"):
            _validate_cross_refs(report, eng)

    def test_no_engagement_path_skips(self) -> None:
        report = SufficiencyReport.model_validate(
            {
                **_insufficient_response(),
                "generated_at": "2024-01-01T00:00:00Z",
                "by": "agent",
            }
        )
        # Should not raise with None engagement
        _validate_cross_refs(report, None)


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


class TestVerdicts:
    def test_sufficient_when_all_known(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_json(_sufficient_response())

        report = run_sufficiency_gate(
            "user-story",
            "Invoice approval",
            transport=transport,
            engagement_path=eng,
        )
        assert report.verdict == SufficiencyVerdict.SUFFICIENT
        assert report.recommended_action == "produce"

    def test_insufficient_when_blocker_unknown(self, eng: Path) -> None:
        from praxis.engagement import StakeholderRepo

        s = StakeholderRepo(eng).add(name="Maria L.", role="AP Manager")

        transport = MockTransport()
        transport.queue_json(_insufficient_response(stakeholder_id=s.id))

        report = run_sufficiency_gate(
            "user-story",
            "Invoice approval",
            transport=transport,
            engagement_path=eng,
        )
        assert report.verdict == SufficiencyVerdict.INSUFFICIENT
        assert report.recommended_action == "elicit"
        assert s.id in report.elicitation_targets

    def test_partial_when_no_blockers_unknown(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_json(_partial_response())

        report = run_sufficiency_gate(
            "spec",
            "Payment module",
            transport=transport,
            engagement_path=eng,
        )
        assert report.verdict == SufficiencyVerdict.PARTIAL
        assert report.recommended_action == "produce_with_caveats"


# ---------------------------------------------------------------------------
# Report persistence
# ---------------------------------------------------------------------------


class TestReportPersistence:
    def test_report_saved_to_disk(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_json(_sufficient_response())

        run_sufficiency_gate(
            "user-story",
            "Invoice approval",
            transport=transport,
            engagement_path=eng,
        )

        reports_dir = eng / ".praxis" / "state" / "sufficiency-reports"
        assert reports_dir.is_dir()
        reports = list(reports_dir.glob("*.json"))
        assert len(reports) == 1

        # Validate the saved report
        saved = json.loads(reports[0].read_text())
        assert saved["verdict"] == "sufficient"
        assert saved["schema_version"] == 1

    def test_no_persistence_without_engagement(self) -> None:
        transport = MockTransport()
        transport.queue_json(_sufficient_response())

        report = run_sufficiency_gate(
            "user-story",
            "Invoice approval",
            transport=transport,
            engagement_path=None,
        )
        assert report.verdict == SufficiencyVerdict.SUFFICIENT


# ---------------------------------------------------------------------------
# Audit event
# ---------------------------------------------------------------------------


class TestAuditEvent:
    def test_audit_emitted(self, eng: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        events: list[dict[str, object]] = []
        original_emit = None

        from praxis.core import sufficiency as suf_module

        original_emit = suf_module.emit

        def capture_emit(event_type: str, **kwargs: object) -> object:
            events.append({"event_type": event_type, **kwargs})
            return original_emit(event_type, **kwargs)

        monkeypatch.setattr(suf_module, "emit", capture_emit)

        transport = MockTransport()
        transport.queue_json(_sufficient_response())

        run_sufficiency_gate(
            "user-story",
            "Invoice approval",
            transport=transport,
            engagement_path=eng,
        )

        suf_events = [e for e in events if e["event_type"] == "sufficiency.evaluated"]
        assert len(suf_events) == 1
        assert suf_events[0]["verdict"] == "sufficient"


# ---------------------------------------------------------------------------
# Schema validation errors
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_invalid_schema_raises(self, eng: Path) -> None:
        transport = MockTransport()
        # Missing required fields
        transport.queue_json({"verdict": "sufficient"})

        with pytest.raises(SufficiencyError, match="schema validation"):
            run_sufficiency_gate(
                "user-story",
                "Test",
                transport=transport,
                engagement_path=eng,
            )

    def test_empty_response_raises(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_raw("")

        with pytest.raises(SufficiencyError):
            run_sufficiency_gate(
                "user-story",
                "Test",
                transport=transport,
                engagement_path=eng,
            )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestModels:
    def test_info_need_status_values(self) -> None:
        assert InfoNeedStatus.KNOWN == "known"
        assert InfoNeedStatus.PARTIAL == "partial"
        assert InfoNeedStatus.UNKNOWN == "unknown"

    def test_verdict_values(self) -> None:
        assert SufficiencyVerdict.SUFFICIENT == "sufficient"
        assert SufficiencyVerdict.PARTIAL == "partial"
        assert SufficiencyVerdict.INSUFFICIENT == "insufficient"

    def test_report_extra_forbid(self) -> None:
        with pytest.raises(Exception):  # noqa: B017, PT011
            SufficiencyReport(
                artifact_kind="test",
                artifact_target="test",
                information_needs=[],
                verdict=SufficiencyVerdict.SUFFICIENT,
                recommended_action="produce",
                reasoning="ok",
                generated_at="2024-01-01T00:00:00Z",
                by="agent",
                unknown_field="bad",
            )

    def test_info_need_round_trip(self) -> None:
        need = InfoNeed(
            need="Actor identity",
            status=InfoNeedStatus.KNOWN,
            have="Finance Manager",
            blocker=True,
        )
        data = need.model_dump(mode="json")
        restored = InfoNeed.model_validate(data)
        assert restored.need == "Actor identity"
        assert restored.status == InfoNeedStatus.KNOWN
