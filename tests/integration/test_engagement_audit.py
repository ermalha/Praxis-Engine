"""Integration test: engagement audit events write to per-engagement log (D-006)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement

runner = CliRunner()


class TestEngagementAudit:
    """D-006: Mutating CLI commands should write audit events to per-engagement JSONL."""

    def test_glossary_add_writes_per_engagement_audit(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "AuditTest")

        result = runner.invoke(
            app,
            [
                "engagement",
                "glossary",
                "add",
                "Widget",
                "A reusable UI component",
                "-e",
                str(tmp_engagement),
            ],
        )
        assert result.exit_code == 0

        audit_path = tmp_engagement / ".praxis" / "state" / "audit.jsonl"
        assert audit_path.exists(), "Per-engagement audit.jsonl should exist"

        lines = audit_path.read_text().strip().splitlines()
        events = [json.loads(line) for line in lines]

        glossary_events = [e for e in events if e["event_type"] == "glossary.term.added"]
        assert len(glossary_events) >= 1, "Expected at least one glossary.term.added event"
        assert glossary_events[0]["engagement"] == "AuditTest"
