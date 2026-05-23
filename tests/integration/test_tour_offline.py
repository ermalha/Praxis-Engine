"""D-049 — Offline-runnable verification of the first-engagement walkthrough.

The README quick-start and ``docs/how-to/first-engagement.md`` claim a
zero-to-working-engagement experience. These tests guard the deterministic,
LLM-free portion of that walkthrough — init, engagement seeding, status,
queue, and the TUI smoke entry point — so the doc cannot silently drift
from reality.

LLM-using steps (ask, check, elicit, artifact generate) are exercised by
the cold-run procedure documented in the how-to itself; they cost real
API tokens and are out of scope for unit-style CI.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from praxis.cli import app

runner = CliRunner()


def _init_engagement(eng: Path, *, name: str = "Test Engagement") -> None:
    """Helper: run ``praxis init`` against *eng* with a deterministic name."""
    result = runner.invoke(
        app,
        ["init", str(eng), "--name", name, "--methodology", "agile"],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")


class TestFirstEngagementTourOffline:
    """One test per non-LLM tour step."""

    def test_step_2_init_creates_documented_layout(
        self, tmp_engagement: Path, tmp_home: Path
    ) -> None:
        """``praxis init`` produces the ``.praxis/`` layout the how-to documents."""
        _init_engagement(tmp_engagement, name="Acme Loan Intake")

        praxis_dir = tmp_engagement / ".praxis"
        assert (praxis_dir / "config.yaml").exists()
        assert (praxis_dir / "engagement" / "stakeholders.yaml").exists()
        assert (praxis_dir / "engagement" / "glossary.yaml").exists()
        assert (praxis_dir / "engagement" / "open-questions.yaml").exists()
        assert (praxis_dir / "engagement" / "risks.yaml").exists()
        assert (praxis_dir / "engagement" / "assumptions-and-constraints.yaml").exists()
        assert (praxis_dir / "engagement" / "decisions").is_dir()

    def test_step_3a_stakeholder_add(self, tmp_engagement: Path, tmp_home: Path) -> None:
        _init_engagement(tmp_engagement)

        result = runner.invoke(
            app,
            [
                "engagement",
                "stakeholder",
                "add",
                "Alice Chen",
                "VP of Lending",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.stdout + (result.stderr or "")
        assert "Alice Chen" in result.stdout

    def test_step_3b_glossary_add(self, tmp_engagement: Path, tmp_home: Path) -> None:
        _init_engagement(tmp_engagement)

        result = runner.invoke(
            app,
            [
                "engagement",
                "glossary",
                "add",
                "Member",
                "A credit-union customer.",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.stdout + (result.stderr or "")

    def test_step_3c_constraint_add(self, tmp_engagement: Path, tmp_home: Path) -> None:
        _init_engagement(tmp_engagement)

        result = runner.invoke(
            app,
            [
                "engagement",
                "constraint",
                "add",
                "Must comply with GLBA.",
                "regulatory",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.stdout + (result.stderr or "")

    def test_step_3d_risk_add(self, tmp_engagement: Path, tmp_home: Path) -> None:
        _init_engagement(tmp_engagement)

        result = runner.invoke(
            app,
            [
                "engagement",
                "risk",
                "add",
                "Vendor sandbox delay",
                "Core banking sandbox takes 2 weeks",
                "-i",
                "medium",
                "-l",
                "medium",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.stdout + (result.stderr or "")

    def test_step_8_status_renders(self, tmp_engagement: Path, tmp_home: Path) -> None:
        """``praxis status`` produces the expected metric table after seeding."""
        _init_engagement(tmp_engagement, name="Acme Loan Intake")
        runner.invoke(
            app,
            ["engagement", "stakeholder", "add", "Alice", "PM", "-e", str(tmp_engagement)],
        )

        result = runner.invoke(app, ["status", "-e", str(tmp_engagement)])

        assert result.exit_code == 0, result.stdout + (result.stderr or "")
        # The status panel title uses the engagement name (D-040).
        assert "Acme Loan Intake" in result.stdout
        # Core metric rows the how-to documents.
        for metric in ("Stakeholders", "Glossary terms", "Open questions"):
            assert metric in result.stdout, f"missing '{metric}' row in status output"

    def test_step_10_tui_smoke_json(self, tmp_engagement: Path, tmp_home: Path) -> None:
        """``praxis tui --smoke`` returns the documented JSON shape."""
        _init_engagement(tmp_engagement)

        result = runner.invoke(app, ["tui", "--smoke", "-e", str(tmp_engagement)])

        assert result.exit_code == 0, result.stdout + (result.stderr or "")
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["screens_loaded"] is True
        # The how-to lists nine screens.
        assert len(payload["available_screens"]) == 9
