"""Integration tests for Chunk 09 — Sufficiency Gate."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.core.sufficiency import SufficiencyVerdict, run_sufficiency_gate
from praxis.engagement import StakeholderRepo
from praxis.errors import SufficiencyError
from praxis.storage.db import close_connection
from praxis.transport.base import Transport
from praxis.transport.models import (
    ChatRequest,
    ProbeResult,
    StreamChunk,
    Usage,
)


class MockTransport(Transport):
    """Transport that returns queued JSON responses."""

    name = "mock"

    def __init__(self) -> None:
        self._queue: list[str] = []

    def queue_json(self, data: dict[str, object]) -> None:
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


class TestSufficiencyGateBlocksOnMissingBlocker:
    def test_full_lifecycle(self, eng: Path) -> None:
        # Add a stakeholder so cross-ref validation passes
        stakeholder = StakeholderRepo(eng).add(
            name="Maria L.",
            role="AP Manager",
        )

        transport = MockTransport()
        transport.queue_json(
            {
                "artifact_kind": "user-story",
                "artifact_target": "Invoice approval workflow",
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
                                "ref": stakeholder.id,
                                "rationale": "AP Manager",
                            }
                        ],
                    }
                ],
                "verdict": "insufficient",
                "recommended_action": "elicit",
                "reasoning": "Threshold value missing",
                "elicitation_targets": [stakeholder.id],
            }
        )

        report = run_sufficiency_gate(
            "user-story",
            "Invoice approval workflow",
            transport=transport,
            engagement_path=eng,
        )

        assert report.verdict == SufficiencyVerdict.INSUFFICIENT
        assert report.recommended_action == "elicit"
        assert stakeholder.id in report.elicitation_targets

        # Verify report was persisted
        reports_dir = eng / ".praxis" / "state" / "sufficiency-reports"
        assert len(list(reports_dir.glob("*.json"))) == 1

    def test_cross_ref_bad_id_rejected(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_json(
            {
                "artifact_kind": "user-story",
                "artifact_target": "Test",
                "information_needs": [
                    {
                        "need": "Something",
                        "status": "unknown",
                        "blocker": True,
                        "candidate_sources": [],
                    }
                ],
                "verdict": "insufficient",
                "recommended_action": "elicit",
                "reasoning": "Missing info",
                "elicitation_targets": ["nonexistent-id"],
            }
        )

        with pytest.raises(SufficiencyError, match="not found"):
            run_sufficiency_gate(
                "user-story",
                "Test",
                transport=transport,
                engagement_path=eng,
            )


class TestSufficientVerdictProduces:
    def test_sufficient_produces(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_json(
            {
                "artifact_kind": "spec",
                "artifact_target": "API design",
                "information_needs": [
                    {
                        "need": "Scope boundaries",
                        "status": "known",
                        "have": "REST API for invoices",
                        "blocker": True,
                        "candidate_sources": [],
                    }
                ],
                "verdict": "sufficient",
                "recommended_action": "produce",
                "reasoning": "All information available.",
            }
        )

        report = run_sufficiency_gate(
            "spec",
            "API design",
            transport=transport,
            engagement_path=eng,
        )

        assert report.verdict == SufficiencyVerdict.SUFFICIENT
        assert report.recommended_action == "produce"
