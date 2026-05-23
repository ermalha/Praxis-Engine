"""D-047 / RW-019: structlog console output routes to stderr, never stdout.

Closes RW-019, which surfaced during the v0.3.0 retest: ``praxis ... --json
| jq`` failed because the audit ``logger.debug("audit.emitted", ...)`` call
emitted to stdout, prefixing the JSON payload with structured-log lines.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from praxis.audit.writer import emit
from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.logging_setup import configure_logging
from praxis.workqueue.models import WorkItemPriority, WorkItemType
from praxis.workqueue.repo import WorkQueueRepo

runner = CliRunner()


class TestStructlogRouting:
    """Direct tests of the structlog configuration: stderr-only, level-gated."""

    def test_default_suppresses_debug_on_both_streams(
        self,
        capsys: pytest.CaptureFixture[str],
        tmp_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without PRAXIS_DEBUG, audit.emit's debug line is filtered out
        entirely — never appears on stdout *or* stderr."""
        monkeypatch.delenv("PRAXIS_DEBUG", raising=False)
        configure_logging(debug=False)

        emit("test.routing.default", actor="system")

        captured = capsys.readouterr()
        assert "audit.emitted" not in captured.out, (
            f"audit.emitted leaked to stdout: {captured.out!r}"
        )
        assert "audit.emitted" not in captured.err, (
            f"audit.emitted leaked to stderr at default level: {captured.err!r}"
        )

    def test_debug_mode_routes_to_stderr_only(
        self,
        capsys: pytest.CaptureFixture[str],
        tmp_home: Path,
    ) -> None:
        """With debug enabled the structured-log line MUST appear on stderr
        and MUST NOT appear on stdout. This is the RW-019 regression guard."""
        try:
            configure_logging(debug=True)
            emit("test.routing.debug", actor="system")

            captured = capsys.readouterr()
            assert "audit.emitted" not in captured.out, (
                f"RW-019 regression: audit.emitted appeared on stdout: {captured.out!r}"
            )
            assert "audit.emitted" in captured.err, (
                f"audit.emitted missing from stderr in debug mode: {captured.err!r}"
            )
        finally:
            # Restore default for any tests that run after us in the same process.
            configure_logging(debug=False)


class TestJsonPipeCleanliness:
    """End-to-end repro of the RW-019 pipeline: ``praxis ... --json | jq``."""

    def test_queue_json_stdout_parses_in_debug_mode(
        self,
        tmp_engagement: Path,
    ) -> None:
        """Even when DEBUG-level structlog is enabled, ``--json`` stdout
        must remain a valid JSON document — debug noise routes to stderr."""
        init_engagement(tmp_engagement, "Test")
        WorkQueueRepo(tmp_engagement).enqueue(
            type=WorkItemType.REVIEW_ARTIFACT,
            assignee="agent",
            title="t",
            description="d",
            priority=WorkItemPriority.MEDIUM,
        )

        try:
            configure_logging(debug=True)
            result = runner.invoke(
                app,
                ["queue", "--all", "--json", "-e", str(tmp_engagement)],
            )

            assert result.exit_code == 0, result.stdout + result.stderr
            # The critical assertion: stdout is parseable JSON.
            json.loads(result.stdout)
        finally:
            configure_logging(debug=False)
