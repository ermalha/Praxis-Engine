"""D-052 — Engagement CLI completeness.

Closes NEW-001 / NEW-004 from the v0.2.0 retest: the
``engagement assumption`` and ``engagement constraint`` subcommands
had only add/list verbs, and ``engagement question open`` could not
attach candidate answerers or blocked-artifact IDs from the CLI even
though the repo accepted them.

These tests cover the new verbs end-to-end via CliRunner: add → get →
update → remove for both assumption and constraint, plus
``question open --answerers --blocks``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.engagement.repos import AssumptionsConstraintsRepo, OpenQuestionsRepo

runner = CliRunner()


def _add_assumption(eng: Path, statement: str = "MVP within 6 months feasible") -> str:
    """Helper: add an assumption via CLI and return its ID."""
    result = runner.invoke(
        app,
        ["engagement", "assumption", "add", statement, "-e", str(eng)],
    )
    assert result.exit_code == 0, result.output
    # The CLI prints "Added assumption [<id>]." — extract the id.
    return AssumptionsConstraintsRepo(eng).list_assumptions()[-1].id


def _add_constraint(eng: Path, statement: str = "Must comply with GLBA") -> str:
    """Helper: add a constraint via CLI and return its ID."""
    result = runner.invoke(
        app,
        ["engagement", "constraint", "add", statement, "regulatory", "-e", str(eng)],
    )
    assert result.exit_code == 0, result.output
    return AssumptionsConstraintsRepo(eng).list_constraints()[-1].id


class TestAssumptionCRUD:
    def test_get_existing(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        aid = _add_assumption(tmp_engagement, "Auth team has bandwidth Q3")

        result = runner.invoke(
            app, ["engagement", "assumption", "get", aid, "-e", str(tmp_engagement)]
        )

        assert result.exit_code == 0, result.output
        assert "Auth team has bandwidth Q3" in result.output
        assert aid in result.output

    def test_get_json(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        aid = _add_assumption(tmp_engagement, "JSON-parseable")

        result = runner.invoke(
            app,
            ["engagement", "assumption", "get", aid, "-e", str(tmp_engagement), "--json"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["id"] == aid
        assert payload["statement"] == "JSON-parseable"

    def test_get_missing_exits_nonzero(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")

        result = runner.invoke(
            app, ["engagement", "assumption", "get", "no-such-id", "-e", str(tmp_engagement)]
        )

        assert result.exit_code != 0
        combined = result.output + (result.stderr or "")
        assert "not found" in combined.lower()

    def test_update_statement_only(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        aid = _add_assumption(tmp_engagement, "Original")

        result = runner.invoke(
            app,
            [
                "engagement",
                "assumption",
                "update",
                aid,
                "--statement",
                "Updated statement",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.output
        a = AssumptionsConstraintsRepo(tmp_engagement).get_assumption(aid)
        assert a.statement == "Updated statement"

    def test_update_preserves_validated_flag(self, tmp_engagement: Path, tmp_home: Path) -> None:
        """Updating mutable fields must NOT clobber the validated state."""
        init_engagement(tmp_engagement, "Test")
        aid = _add_assumption(tmp_engagement)
        repo = AssumptionsConstraintsRepo(tmp_engagement)
        repo.validate_assumption(aid)

        result = runner.invoke(
            app,
            [
                "engagement",
                "assumption",
                "update",
                aid,
                "--rationale",
                "Sponsor confirmed",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0
        a = repo.get_assumption(aid)
        assert a.validated is True
        assert a.rationale == "Sponsor confirmed"

    def test_remove(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        aid = _add_assumption(tmp_engagement)

        result = runner.invoke(
            app,
            ["engagement", "assumption", "remove", aid, "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0, result.output
        repo = AssumptionsConstraintsRepo(tmp_engagement)
        assert all(a.id != aid for a in repo.list_assumptions())


class TestConstraintCRUD:
    def test_get_existing(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        cid = _add_constraint(tmp_engagement, "Must support mobile browsers")

        result = runner.invoke(
            app, ["engagement", "constraint", "get", cid, "-e", str(tmp_engagement)]
        )

        assert result.exit_code == 0
        assert "Must support mobile browsers" in result.output
        assert cid in result.output

    def test_update_type_and_source(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        cid = _add_constraint(tmp_engagement)

        result = runner.invoke(
            app,
            [
                "engagement",
                "constraint",
                "update",
                cid,
                "--type",
                "business",
                "--source",
                "Sponsor",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.output
        c = AssumptionsConstraintsRepo(tmp_engagement).get_constraint(cid)
        assert c.constraint_type == "business"
        assert c.source == "Sponsor"

    def test_remove(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        cid = _add_constraint(tmp_engagement)

        result = runner.invoke(
            app,
            ["engagement", "constraint", "remove", cid, "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0, result.output
        repo = AssumptionsConstraintsRepo(tmp_engagement)
        assert all(c.id != cid for c in repo.list_constraints())

    def test_remove_missing_exits_nonzero(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")

        result = runner.invoke(
            app,
            ["engagement", "constraint", "remove", "no-such-id", "-e", str(tmp_engagement)],
        )

        assert result.exit_code != 0
        combined = result.output + (result.stderr or "")
        assert "not found" in combined.lower()


class TestQuestionOpenAnswerersAndBlocks:
    @pytest.fixture
    def stakeholder_id(self, tmp_engagement: Path, tmp_home: Path) -> str:
        """Init engagement + add a stakeholder so candidate_answerers validates."""
        init_engagement(tmp_engagement, "Test")
        result = runner.invoke(
            app,
            [
                "engagement",
                "stakeholder",
                "add",
                "Devon Price",
                "Product Manager",
                "-e",
                str(tmp_engagement),
            ],
        )
        assert result.exit_code == 0
        # ID format: "<slug>-<short_hash>"; the slug is "devon-price"
        # so grep for the embedded id substring printed in output.
        # Easier: read the stakeholders file.
        from praxis.engagement.repos.stakeholders import StakeholderRepo

        return StakeholderRepo(tmp_engagement).list_all()[-1].id

    def test_open_with_answerers_and_blocks(
        self,
        tmp_engagement: Path,
        tmp_home: Path,
        stakeholder_id: str,
    ) -> None:
        result = runner.invoke(
            app,
            [
                "engagement",
                "question",
                "open",
                "What is the DTI threshold?",
                "--why",
                "Eligibility business rule",
                "--priority",
                "critical",
                "--answerers",
                stakeholder_id,
                "--blocks",
                "spec-abc123,backlog-xyz789",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.output
        questions = OpenQuestionsRepo(tmp_engagement).list_all()
        assert len(questions) == 1
        q = questions[0]
        assert q.candidate_answerers == [stakeholder_id]
        assert q.blocks == ["spec-abc123", "backlog-xyz789"]

    def test_open_without_new_flags_still_works(self, tmp_engagement: Path, tmp_home: Path) -> None:
        """Regression: the new options are optional; existing CLI usage unchanged."""
        init_engagement(tmp_engagement, "Test")

        result = runner.invoke(
            app,
            [
                "engagement",
                "question",
                "open",
                "Generic question",
                "--why",
                "context",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.output
        q = OpenQuestionsRepo(tmp_engagement).list_all()[-1]
        assert q.candidate_answerers == []
        assert q.blocks == []
