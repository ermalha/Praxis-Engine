"""Integration tests for CLI error handling (D-011).

Verifies that ``PraxisError`` subclasses produce clean user-facing messages
without raw Python tracebacks.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement

runner = CliRunner()


class TestMalformedYAMLNoTraceback:
    """D-011: Malformed YAML should produce a clean error, not a traceback."""

    def test_glossary_list_malformed_yaml(self, tmp_engagement: Path) -> None:
        """Corrupting the glossary YAML should show a clean error."""
        init_engagement(tmp_engagement, "Test")
        glossary_path = tmp_engagement / ".praxis" / "engagement" / "glossary.yaml"
        glossary_path.write_text(": bad: yaml: {{")

        result = runner.invoke(app, ["engagement", "glossary", "list", "-e", str(tmp_engagement)])
        assert result.exit_code == 1
        assert "Traceback" not in result.output
