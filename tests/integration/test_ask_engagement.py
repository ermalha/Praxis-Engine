"""Integration tests for ``praxis ask`` engagement-aware behavior (D-028)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.engagement.repos import DecisionRepo

from .conftest import StubTransport

runner = CliRunner()


class TestAskEngagement:
    def test_ask_with_engagement_injects_system_message(
        self,
        tmp_engagement: Path,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When -e is supplied, the outgoing request leads with a system
        message containing the engagement digest and the flag-uncertainty
        guard."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        init_engagement(tmp_engagement, "Northstar Pilot")
        DecisionRepo(tmp_engagement).create(
            title="MVP: personal loans only",
            context="Sponsor decision",
            decision="Personal loans only; auto loans out of scope.",
            consequences="Backlog sized for personal loans.",
        )

        result = runner.invoke(
            app,
            [
                "ask",
                "-p",
                realworld_profile,
                "-e",
                str(tmp_engagement),
                "What is in scope?",
            ],
        )

        assert result.exit_code == 0, result.output
        assert len(stub_transport.requests) == 1
        msgs = stub_transport.requests[0].messages
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert "Northstar Pilot" in msgs[0].content
        assert "MVP: personal loans only" in msgs[0].content
        assert "do NOT invent" in msgs[0].content
        assert msgs[1].role == "user"
        assert msgs[1].content == "What is in scope?"

    def test_ask_without_engagement_no_system_message(
        self,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Behavior unchanged when -e is omitted: only the user message goes
        out."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        result = runner.invoke(
            app,
            ["ask", "-p", realworld_profile, "Hello"],
        )

        assert result.exit_code == 0, result.output
        assert len(stub_transport.requests) == 1
        msgs = stub_transport.requests[0].messages
        assert len(msgs) == 1
        assert msgs[0].role == "user"
        assert msgs[0].content == "Hello"

    def test_ask_unknown_engagement_path_errors_cleanly(
        self,
        tmp_path: Path,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A bogus -e path exits non-zero with a clean error (no traceback)."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        bogus = tmp_path / "does-not-exist"

        result = runner.invoke(
            app,
            ["ask", "-p", realworld_profile, "-e", str(bogus), "Hi"],
        )

        assert result.exit_code == 1
        combined = result.output + (result.stderr if result.stderr else "")
        assert "Traceback" not in combined
        assert stub_transport.requests == []
