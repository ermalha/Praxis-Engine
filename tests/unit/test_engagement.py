"""Tests for engagement model — repos, models, cross-references."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.engagement import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    GlossaryRepo,
    OpenQuestionsRepo,
    RiskRepo,
    StakeholderRepo,
    SystemLandscapeRepo,
    TimelineRepo,
)
from praxis.errors import EngagementError
from praxis.storage.db import close_connection

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


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------


class TestGlossary:
    def test_add_and_get(self, eng: Path) -> None:
        repo = GlossaryRepo(eng)
        t = repo.add_term("invoice", "A request for payment")
        assert t.term == "invoice"
        assert repo.get("invoice") is not None
        assert repo.get("Invoice") is not None  # case-insensitive

    def test_find(self, eng: Path) -> None:
        repo = GlossaryRepo(eng)
        repo.add_term("invoice", "A request for payment")
        repo.add_term("credit note", "Reversal of an invoice", synonyms=["CN"])
        assert len(repo.find("invoice")) == 1
        assert len(repo.find("cn")) == 1  # searches synonyms

    def test_update(self, eng: Path) -> None:
        repo = GlossaryRepo(eng)
        repo.add_term("invoice", "old def")
        t = repo.update_term("invoice", definition="new def")
        assert t.definition == "new def"

    def test_remove(self, eng: Path) -> None:
        repo = GlossaryRepo(eng)
        repo.add_term("invoice", "def")
        repo.remove_term("invoice")
        assert repo.get("invoice") is None

    def test_duplicate_raises(self, eng: Path) -> None:
        repo = GlossaryRepo(eng)
        repo.add_term("invoice", "def")
        with pytest.raises(EngagementError, match="already exists"):
            repo.add_term("invoice", "def2")

    def test_update_nonexistent(self, eng: Path) -> None:
        repo = GlossaryRepo(eng)
        with pytest.raises(EngagementError, match="not found"):
            repo.update_term("nonexistent", definition="x")

    def test_remove_nonexistent(self, eng: Path) -> None:
        repo = GlossaryRepo(eng)
        with pytest.raises(EngagementError, match="not found"):
            repo.remove_term("nonexistent")


# ---------------------------------------------------------------------------
# Stakeholders
# ---------------------------------------------------------------------------


class TestStakeholders:
    def test_add_and_get(self, eng: Path) -> None:
        repo = StakeholderRepo(eng)
        s = repo.add("Maria L.", "Finance Manager", expertise=["AP"])
        assert s.id
        assert repo.get(s.id) is not None

    def test_list(self, eng: Path) -> None:
        repo = StakeholderRepo(eng)
        repo.add("Alice", "PM")
        repo.add("Bob", "Dev Lead")
        assert len(repo.list_all()) == 2

    def test_update(self, eng: Path) -> None:
        repo = StakeholderRepo(eng)
        s = repo.add("Alice", "PM")
        updated = repo.update(s.id, role="Senior PM")
        assert updated.role == "Senior PM"

    def test_remove(self, eng: Path) -> None:
        repo = StakeholderRepo(eng)
        s = repo.add("Alice", "PM")
        repo.remove(s.id)
        assert repo.get(s.id) is None

    def test_exists(self, eng: Path) -> None:
        repo = StakeholderRepo(eng)
        s = repo.add("Alice", "PM")
        assert repo.exists(s.id)
        assert not repo.exists("nonexistent")


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


class TestDecisions:
    def test_create_and_get(self, eng: Path) -> None:
        repo = DecisionRepo(eng)
        d = repo.create(
            title="Use PostgreSQL",
            context="Need a database",
            decision="PostgreSQL",
            consequences="Team must learn PG",
        )
        assert d.id.startswith("ADR-")
        result = repo.get(d.id)
        assert result is not None
        fm, body = result
        assert fm.title == "Use PostgreSQL"
        assert "Context" in body

    def test_create_with_stakeholder_ref(self, eng: Path) -> None:
        s_repo = StakeholderRepo(eng)
        s = s_repo.add("Alice", "PM")

        d_repo = DecisionRepo(eng)
        d = d_repo.create(
            title="Auth approach",
            context="Need auth",
            decision="OAuth2",
            consequences="Need IDP",
            decided_by=[s.id],
        )
        assert s.id in d.decided_by

    def test_dangling_stakeholder_ref_raises(self, eng: Path) -> None:
        repo = DecisionRepo(eng)
        with pytest.raises(EngagementError, match="not found"):
            repo.create(
                title="Bad ref",
                context="ctx",
                decision="dec",
                consequences="cons",
                decided_by=["does-not-exist"],
            )

    def test_list(self, eng: Path) -> None:
        repo = DecisionRepo(eng)
        repo.create("D1", "c", "d", "con")
        repo.create("D2", "c", "d", "con")
        assert len(repo.list_all()) == 2

    def test_supersede(self, eng: Path) -> None:
        repo = DecisionRepo(eng)
        d1 = repo.create("Original", "c", "d", "con")
        d2 = repo.create("Replacement", "c", "d", "con")
        updated = repo.supersede(d1.id, d2.id)
        assert updated.status == "superseded"
        assert updated.superseded_by == d2.id

    def test_file_exists(self, eng: Path) -> None:
        repo = DecisionRepo(eng)
        d = repo.create("File test", "c", "d", "con")
        path = eng / ".praxis" / "engagement" / "decisions" / f"{d.id}.md"
        assert path.exists()


# ---------------------------------------------------------------------------
# Open Questions
# ---------------------------------------------------------------------------


class TestOpenQuestions:
    def test_open_and_list(self, eng: Path) -> None:
        repo = OpenQuestionsRepo(eng)
        q = repo.open("What is the deadline?", "Blocks planning")
        assert q.status == "open"
        assert len(repo.list_all()) == 1

    def test_answer(self, eng: Path) -> None:
        repo = OpenQuestionsRepo(eng)
        q = repo.open("When?", "Blocks work")
        answered = repo.answer(q.id, "Next Friday")
        assert answered.status == "answered"
        assert answered.answer == "Next Friday"

    def test_withdraw(self, eng: Path) -> None:
        repo = OpenQuestionsRepo(eng)
        q = repo.open("Obsolete?", "Maybe not relevant")
        w = repo.withdraw(q.id)
        assert w.status == "withdrawn"

    def test_filter_by_status(self, eng: Path) -> None:
        repo = OpenQuestionsRepo(eng)
        repo.open("Q1", "M1")
        q2 = repo.open("Q2", "M2")
        repo.answer(q2.id, "Done")
        assert len(repo.list_all(status="open")) == 1
        assert len(repo.list_all(status="answered")) == 1

    def test_dangling_answerer_ref(self, eng: Path) -> None:
        repo = OpenQuestionsRepo(eng)
        with pytest.raises(EngagementError, match="not found"):
            repo.open("Bad ref", "test", candidate_answerers=["does-not-exist"])

    def test_valid_answerer_ref(self, eng: Path) -> None:
        s_repo = StakeholderRepo(eng)
        s = s_repo.add("Maria", "FM")
        q_repo = OpenQuestionsRepo(eng)
        q = q_repo.open("Q?", "test", candidate_answerers=[s.id])
        assert s.id in q.candidate_answerers


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------


class TestSystems:
    def test_add_and_list(self, eng: Path) -> None:
        repo = SystemLandscapeRepo(eng)
        s = repo.add("CRM", "web app", description="Customer management")
        assert s.id
        assert len(repo.list_all()) == 1

    def test_update(self, eng: Path) -> None:
        repo = SystemLandscapeRepo(eng)
        s = repo.add("CRM", "web app")
        updated = repo.update(s.id, status="deprecated")
        assert updated.status == "deprecated"


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------


class TestRisks:
    def test_add_and_list(self, eng: Path) -> None:
        repo = RiskRepo(eng)
        r = repo.add("Vendor lock-in", "Single cloud provider", "medium", "high")
        assert r.id
        assert len(repo.list_all()) == 1

    def test_close(self, eng: Path) -> None:
        repo = RiskRepo(eng)
        r = repo.add("Risk", "Desc", "low", "low")
        closed = repo.close(r.id)
        assert closed.status == "closed"


# ---------------------------------------------------------------------------
# Assumptions & Constraints
# ---------------------------------------------------------------------------


class TestAssumptionsConstraints:
    def test_add_assumption(self, eng: Path) -> None:
        repo = AssumptionsConstraintsRepo(eng)
        a = repo.add_assumption("Users have internet", rationale="Cloud-based app")
        assert a.id
        assert len(repo.list_assumptions()) == 1

    def test_add_constraint(self, eng: Path) -> None:
        repo = AssumptionsConstraintsRepo(eng)
        c = repo.add_constraint("Must use AWS", "technical", source="CTO mandate")
        assert c.id
        assert len(repo.list_constraints()) == 1

    def test_validate_assumption(self, eng: Path) -> None:
        repo = AssumptionsConstraintsRepo(eng)
        a = repo.add_assumption("Users have internet")
        v = repo.validate_assumption(a.id)
        assert v.validated is True

    def test_invalidate_assumption(self, eng: Path) -> None:
        repo = AssumptionsConstraintsRepo(eng)
        a = repo.add_assumption("Users have internet")
        inv = repo.invalidate_assumption(a.id)
        assert inv.invalidated_at is not None


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


class TestTimeline:
    def test_add_and_list(self, eng: Path) -> None:
        repo = TimelineRepo(eng)
        m = repo.add("MVP Launch", date(2026, 6, 1))
        assert m.id
        assert len(repo.list_all()) == 1

    def test_update(self, eng: Path) -> None:
        repo = TimelineRepo(eng)
        m = repo.add("Launch", date(2026, 6, 1))
        updated = repo.update(m.id, status="achieved")
        assert updated.status == "achieved"
