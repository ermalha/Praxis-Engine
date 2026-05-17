"""Unit tests for ``praxis.engagement.digest.build_engagement_digest``."""

from __future__ import annotations

from pathlib import Path

from praxis.config.engagement import init_engagement
from praxis.engagement import build_engagement_digest
from praxis.engagement.repos import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    OpenQuestionsRepo,
    StakeholderRepo,
)


def _seed(eng: Path) -> None:
    """Seed an engagement with one of each entity type used by the digest."""
    init_engagement(eng, "Test Engagement")

    StakeholderRepo(eng).add(name="Alice Chen", role="Sponsor")
    DecisionRepo(eng).create(
        title="MVP scope: personal loans only",
        context="Sponsor confirmed scope",
        decision="MVP covers personal loans only; auto loans deferred.",
        consequences="Backlog sized for personal loans only.",
    )
    AssumptionsConstraintsRepo(eng).add_constraint(
        statement="Must comply with GLBA",
        constraint_type="regulatory",
    )
    OpenQuestionsRepo(eng).open(
        question="What document types are required for self-employed applicants?",
        why_it_matters="Drives form design and validation rules.",
        priority="critical",
    )


class TestBuildEngagementDigest:
    def test_digest_includes_all_sections_with_seeded_data(self, tmp_engagement: Path) -> None:
        _seed(tmp_engagement)

        name, digest = build_engagement_digest(tmp_engagement)

        assert name == "Test Engagement"
        assert "# Engagement: Test Engagement" in digest
        assert "## Recent decisions" in digest
        assert "MVP scope: personal loans only" in digest
        assert "## Top constraints" in digest
        assert "Must comply with GLBA" in digest
        assert "(regulatory)" in digest
        assert "## Open questions" in digest
        assert "self-employed" in digest
        assert "[critical]" in digest
        assert "## Stakeholders" in digest
        assert "Alice Chen (Sponsor)" in digest

    def test_digest_handles_empty_engagement(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Empty Project")

        name, digest = build_engagement_digest(tmp_engagement)

        assert name == "Empty Project"
        assert "# Engagement: Empty Project" in digest
        # All section headers present even when empty
        assert "## Recent decisions" in digest
        assert "## Top constraints" in digest
        assert "## Open questions" in digest
        assert "## Stakeholders" in digest
        # Each empty section shows "- (none)" — 4 total
        assert digest.count("- (none)") == 4

    def test_digest_truncates_long_decision_body(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Trunc Test")
        long_body = "x" * 500
        DecisionRepo(tmp_engagement).create(
            title="Long decision",
            context="ctx",
            decision=long_body,
            consequences="conseq",
        )

        _, digest = build_engagement_digest(tmp_engagement)

        # Body cap is 200; truncated entries end with the ellipsis character.
        assert "…" in digest
        # The raw 500-x string should not appear verbatim in the digest.
        assert long_body not in digest

    def test_digest_excludes_answered_questions(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Q Filter Test")
        repo = OpenQuestionsRepo(tmp_engagement)
        opened = repo.open(question="Still open?", why_it_matters="x")
        answered = repo.open(question="Closed already?", why_it_matters="x")
        repo.answer(answered.id, "yes")

        _, digest = build_engagement_digest(tmp_engagement)

        assert "Still open?" in digest
        assert "Closed already?" not in digest
        assert opened.id  # silence unused warning; just ensures fixture worked
