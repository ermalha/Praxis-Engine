"""Integration test for Chunk 07 — Engagement Model API.

Full lifecycle: glossary, stakeholder, decision, question with cross-refs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.engagement import (
    DecisionRepo,
    GlossaryRepo,
    OpenQuestionsRepo,
    StakeholderRepo,
)
from praxis.errors import EngagementError
from praxis.storage.db import close_connection


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


class TestFullEngagementLifecycle:
    def test_full_lifecycle(self, eng: Path) -> None:
        glossary = GlossaryRepo(eng)
        stakeholders = StakeholderRepo(eng)
        decisions = DecisionRepo(eng)
        questions = OpenQuestionsRepo(eng)

        # 1. Add a glossary term
        t = glossary.add_term("invoice", "A request for payment for goods or services")
        assert t.term == "invoice"
        assert glossary.find("invoice")[0].term == "invoice"

        # 2. Add a stakeholder
        s = stakeholders.add(
            name="Maria L.",
            role="Finance Manager",
            expertise=["accounts payable"],
            decision_authority=["invoice approval thresholds"],
        )
        assert s.id

        # 3. Open a question that references Maria
        q = questions.open(
            question="What's the AP threshold for invoices?",
            why_it_matters="Blocks story BA-101",
            candidate_answerers=[s.id],
        )
        assert q.status == "open"

        # 4. Reject dangling reference
        with pytest.raises(EngagementError):
            questions.open(
                question="Bad ref",
                why_it_matters="test",
                candidate_answerers=["does-not-exist"],
            )

        # 5. Create a decision
        d = decisions.create(
            title="Approval threshold = 10k",
            context="Need to define AP thresholds",
            decision="Set threshold at 10k",
            consequences="Invoices above 10k need VP approval",
            decided_by=[s.id],
        )
        assert d.id.startswith("ADR-")
        assert (eng / ".praxis" / "engagement" / "decisions" / f"{d.id}.md").exists()

        # 6. Answer the question
        answered = questions.answer(q.id, "Threshold is 10k per ADR")
        assert answered.status == "answered"
        assert answered.answer is not None
