"""Integration test for `artifact list --profile` consistency (D-041).

Closes RW-008. `artifact list` rejected ``--profile`` (`No such option`)
while `artifact generate` (and every other BA-surface command) accepted
it. Now accepted as a no-op for CLI consistency — listing is a
filesystem read and doesn't need a profile.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement

runner = CliRunner()


class TestArtifactListProfile:
    def test_artifact_list_accepts_profile_flag(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        result = runner.invoke(
            app,
            ["artifact", "list", "--profile", "foo", "-e", str(tmp_engagement)],
        )
        assert result.exit_code == 0, result.output
        # No "No such option" error
        combined = result.output + (result.stderr if result.stderr else "")
        assert "No such option" not in combined

    def test_artifact_list_works_without_profile(self, tmp_engagement: Path) -> None:
        """Regression: omitting --profile still works (no required-option introduced)."""
        init_engagement(tmp_engagement, "Test")
        result = runner.invoke(app, ["artifact", "list", "-e", str(tmp_engagement)])
        assert result.exit_code == 0, result.output
