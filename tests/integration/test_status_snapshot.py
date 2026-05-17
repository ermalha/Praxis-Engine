"""Integration tests for the expanded `praxis status` snapshot (D-040).

Closes RW-005. The original status panel:
  - titled itself with the engagement directory name (literal "engagement" in
    the v0.2.0 real-world test) instead of the configured engagement name
  - only showed 3 metrics (Stakeholders, Open questions, Active work-items)

After D-040:
  - title uses ``load_engagement_config(eng).name``
  - table covers all entity types + work-item splits + last sufficiency
  - a second panel lists the top 3 critical open questions when present
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.engagement.repos import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    GlossaryRepo,
    OpenQuestionsRepo,
    RiskRepo,
    StakeholderRepo,
)

runner = CliRunner()


def _seed_one_of_each(eng: Path) -> None:
    """Seed one of each entity type so all status rows are non-zero."""
    StakeholderRepo(eng).add(name="Alice", role="Sponsor")
    GlossaryRepo(eng).add_term("Member", "A credit-union customer")
    DecisionRepo(eng).create(
        title="MVP scope",
        context="ctx",
        decision="Personal loans only",
        consequences="cons",
    )
    AssumptionsConstraintsRepo(eng).add_constraint(
        statement="GLBA compliance",
        constraint_type="regulatory",
    )
    AssumptionsConstraintsRepo(eng).add_assumption(statement="OIDC supported")
    RiskRepo(eng).add(
        title="Vendor delay",
        description="Vendor sandbox takes 2 weeks",
        impact="medium",
        likelihood="medium",
    )


class TestStatusSnapshot:
    def test_status_uses_engagement_name(self, tmp_engagement: Path) -> None:
        """Title pulls from config.name, not the directory name."""
        init_engagement(tmp_engagement, "Acme Loan Intake")

        result = runner.invoke(app, ["status", "-e", str(tmp_engagement)])

        assert result.exit_code == 0, result.output
        assert "Acme Loan Intake" in result.output
        # The dir name happens to differ from the engagement name in this
        # fixture (tmp_engagement.name == "test-engagement"); confirm the
        # config name takes precedence.
        assert "Engagement Status: test-engagement" not in result.output

    def test_status_includes_all_entity_counts(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        _seed_one_of_each(tmp_engagement)

        result = runner.invoke(app, ["status", "-e", str(tmp_engagement)])
        assert result.exit_code == 0, result.output

        # Each new label must appear in the table.
        for label in [
            "Stakeholders",
            "Glossary terms",
            "Decisions",
            "Constraints",
            "Assumptions",
            "Risks",
            "Open questions",
            "Human work-items",
            "Agent work-items",
        ]:
            assert label in result.output, f"missing label: {label}"

    def test_status_json_includes_all_fields(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test JSON")
        _seed_one_of_each(tmp_engagement)

        result = runner.invoke(app, ["status", "-e", str(tmp_engagement), "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)

        for key in [
            "name",
            "stakeholders",
            "glossary",
            "decisions",
            "constraints",
            "assumptions",
            "risks",
            "questions_open",
            "questions_total",
            "workitems_human_active",
            "workitems_human_total",
            "workitems_agent_active",
            "workitems_agent_total",
            "last_wake",
            "last_sufficiency",
        ]:
            assert key in data, f"missing key: {key}"

        assert data["name"] == "Test JSON"
        assert data["stakeholders"] == 1
        assert data["glossary"] == 1
        assert data["decisions"] == 1
        assert data["constraints"] == 1
        assert data["assumptions"] == 1
        assert data["risks"] == 1

    def test_status_top_critical_panel_when_present(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        qrepo = OpenQuestionsRepo(tmp_engagement)
        # One critical and one medium — only the critical should be listed.
        crit = qrepo.open(
            question="What is the launch deadline?",
            why_it_matters="Drives scope choices",
            priority="critical",
        )
        qrepo.open(
            question="What's our DTI threshold?",
            why_it_matters="Eligibility rule",
            priority="medium",
        )

        result = runner.invoke(app, ["status", "-e", str(tmp_engagement)])
        assert result.exit_code == 0, result.output

        assert "Top critical open questions" in result.output
        assert crit.id in result.output
        # The medium-priority question's text should NOT appear in the critical panel
        # (it can still appear in the Open questions count, but the panel is critical-only).
        # We check by absence of the question text below the panel header.
        panel_section = result.output.split("Top critical open questions")[1]
        assert "DTI threshold" not in panel_section

    def test_status_no_critical_panel_when_none(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        OpenQuestionsRepo(tmp_engagement).open(
            question="What's our DTI threshold?",
            why_it_matters="x",
            priority="medium",
        )

        result = runner.invoke(app, ["status", "-e", str(tmp_engagement)])
        assert result.exit_code == 0, result.output
        assert "Top critical open questions" not in result.output
