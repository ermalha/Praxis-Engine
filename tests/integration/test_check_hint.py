"""Integration tests for `praxis check` next-step hint (D-036).

Closes RW-003: `check` was a dead-end for new users. It printed a
sufficiency report and elicitation_targets but never told the user to
actually run `praxis elicit --latest`. The new behavior prints a single
``Next:`` line pointing at the exact next command, gated on
``verdict == insufficient``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.core.sufficiency import (
    InfoNeed,
    InfoNeedStatus,
    SufficiencyReport,
    SufficiencyVerdict,
)

from .conftest import StubTransport

runner = CliRunner()


def _fake_report(verdict: SufficiencyVerdict) -> SufficiencyReport:
    return SufficiencyReport(
        artifact_kind="spec",
        artifact_target="MVP functional requirements",
        information_needs=[
            InfoNeed(
                need="Scope boundaries",
                status=InfoNeedStatus.UNKNOWN,
                blocker=True,
                missing="In/out of scope not yet defined",
            )
        ],
        verdict=verdict,
        recommended_action="elicit" if verdict == SufficiencyVerdict.INSUFFICIENT else "produce",
        reasoning="Test reasoning.",
        elicitation_targets=["stakeholder-a"] if verdict == SufficiencyVerdict.INSUFFICIENT else [],
        generated_at=datetime.now(UTC),
        by="agent",
    )


def _patch_gate(monkeypatch: pytest.MonkeyPatch, verdict: SufficiencyVerdict) -> SufficiencyReport:
    """Replace `run_sufficiency_gate` in check_cmd with one that returns a fake."""
    report = _fake_report(verdict)

    def fake_gate(*_args: object, **_kwargs: object) -> SufficiencyReport:
        return report

    monkeypatch.setattr("praxis.cli.check_cmd.run_sufficiency_gate", fake_gate)
    return report


class TestCheckHint:
    def test_check_prints_elicit_hint_on_insufficient(
        self,
        tmp_engagement: Path,
        stub_transport: StubTransport,  # noqa: ARG002 — registers active profile env
        realworld_profile: str,  # noqa: ARG002 — same
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        init_engagement(tmp_engagement, "Test")
        _patch_gate(monkeypatch, SufficiencyVerdict.INSUFFICIENT)

        result = runner.invoke(
            app,
            ["check", "spec", "MVP functional requirements", "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0, result.output
        assert "Next:" in result.output
        assert "praxis elicit --latest -e" in result.output
        # Engagement path appears too — but Rich may wrap it across lines, so
        # check just the unique trailing dir name.
        assert tmp_engagement.name in result.output

    def test_check_no_hint_when_sufficient(
        self,
        tmp_engagement: Path,
        stub_transport: StubTransport,  # noqa: ARG002
        realworld_profile: str,  # noqa: ARG002
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        init_engagement(tmp_engagement, "Test")
        _patch_gate(monkeypatch, SufficiencyVerdict.SUFFICIENT)

        result = runner.invoke(
            app,
            ["check", "spec", "MVP functional requirements", "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0, result.output
        assert "praxis elicit" not in result.output

    def test_check_no_hint_in_json_mode(
        self,
        tmp_engagement: Path,
        stub_transport: StubTransport,  # noqa: ARG002
        realworld_profile: str,  # noqa: ARG002
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--json output is for machines; no human-facing hint should appear."""
        init_engagement(tmp_engagement, "Test")
        _patch_gate(monkeypatch, SufficiencyVerdict.INSUFFICIENT)

        result = runner.invoke(
            app,
            [
                "check",
                "spec",
                "MVP functional requirements",
                "-e",
                str(tmp_engagement),
                "--json",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Next:" not in result.output
        assert "praxis elicit" not in result.output
