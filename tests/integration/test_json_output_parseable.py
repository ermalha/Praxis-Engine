"""Integration tests verifying all --json CLI outputs are valid JSON (D-030).

Closes RW-017: Rich Console wraps long string values to terminal width even
for non-TTY output, inserting raw newline bytes inside JSON string literals
and breaking ``json.loads``. Each ``--json`` path must now write canonical
JSON via ``typer.echo`` so downstream tools (jq, python -m json.tool, …)
can parse the output reliably.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.engagement.repos import RiskRepo
from praxis.workqueue.models import WorkItemPriority, WorkItemType
from praxis.workqueue.repo import WorkQueueRepo

runner = CliRunner()

# A string long enough to exceed Rich's default 80-col wrap on any value.
_LONG_TEXT = (
    "this is a deliberately very long description that exceeds the rich "
    "console default 80-column wrap threshold so that any internal newline "
    "insertion by the rich rendering pipeline would break json parsing of "
    "the surrounding payload — the regression is real and the test catches it"
)


class TestJsonOutputParseable:
    def test_queue_json_with_long_description_parses(self, tmp_engagement: Path) -> None:
        """The original RW-017 repro: long workitem description must not break
        ``praxis queue --all --json``."""
        init_engagement(tmp_engagement, "Test")
        WorkQueueRepo(tmp_engagement).enqueue(
            type=WorkItemType.REVIEW_ARTIFACT,
            assignee="agent",
            title="long-desc item",
            description=_LONG_TEXT,
            priority=WorkItemPriority.MEDIUM,
        )

        result = runner.invoke(app, ["queue", "--all", "--json", "-e", str(tmp_engagement)])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert isinstance(payload, list)
        assert len(payload) == 1
        assert payload[0]["description"] == _LONG_TEXT

    def test_engagement_risk_list_json_parses(self, tmp_engagement: Path) -> None:
        """``engagement risk list --json`` with long risk description."""
        init_engagement(tmp_engagement, "Test")
        RiskRepo(tmp_engagement).add(
            title="Long risk",
            description=_LONG_TEXT,
            impact="high",
            likelihood="medium",
        )

        result = runner.invoke(
            app,
            ["engagement", "risk", "list", "--json", "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert isinstance(payload, list)
        assert len(payload) == 1
        assert payload[0]["description"] == _LONG_TEXT

    def test_tool_describe_json_parses(self) -> None:
        """``tool describe workqueue_enqueue`` JSON schema output."""
        result = runner.invoke(app, ["tool", "describe", "workqueue_enqueue"])

        assert result.exit_code == 0, result.output
        # tool describe prints both header lines AND a JSON schema.
        # The JSON starts with the first '{' on its own line.
        json_start = result.output.find("{")
        assert json_start != -1, result.output
        payload = json.loads(result.output[json_start:])
        assert payload["type"] == "object"
        assert "properties" in payload

    def test_skill_list_json_parses(self) -> None:
        """``skill list --json`` produces parseable JSON (possibly empty list)."""
        result = runner.invoke(app, ["skill", "list", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert isinstance(payload, list)

    def test_artifact_list_json_parses(self, tmp_engagement: Path) -> None:
        """``artifact list --json`` on a fresh engagement parses to empty list."""
        init_engagement(tmp_engagement, "Test")

        result = runner.invoke(app, ["artifact", "list", "-e", str(tmp_engagement), "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert isinstance(payload, list)

    # Note: wake/run/check/elicit JSON paths are fixed in code at run_cmd.py
    # lines 89, 120, 190, check_cmd.py:72, and elicit_cmd.py:101. Testing them
    # via CliRunner requires non-trivial orchestrator/sufficiency setup; the
    # five tests above cover the underlying pattern (Rich → typer.echo) across
    # the engagement, queue, tool, skill, and artifact surfaces.
