"""Integration tests for ``praxis ask`` engagement-aware behavior (D-028)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.config.models import ModelConfig, Provider
from praxis.config.profiles import create_profile, save_profile
from praxis.engagement.repos import DecisionRepo
from praxis.transport import ChatRequest, ChatResponse

runner = CliRunner()


class _StubTransport:
    """Fake transport that records incoming requests and returns canned text."""

    name = "stub"

    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        return ChatResponse(content="stub-response", finish_reason="stop")


@pytest.fixture()
def stub_transport(monkeypatch: pytest.MonkeyPatch) -> _StubTransport:
    """Replace ``make_transport`` inside ask_cmd with a recording stub."""
    stub = _StubTransport()

    def fake_make_transport(_model_config: object) -> _StubTransport:
        return stub

    monkeypatch.setattr("praxis.cli.ask_cmd.make_transport", fake_make_transport)
    return stub


@pytest.fixture()
def realworld_profile(tmp_home: Path) -> str:
    """Create a profile with a default model so ``ask`` can resolve transport.

    The transport is stubbed in `stub_transport`, so the actual model/key
    are placeholders.
    """
    profile = create_profile("realworld")
    profile.model_aliases["default"] = ModelConfig(
        provider=Provider.OPENAI,
        model="gpt-test",
        api_key_env="OPENAI_API_KEY",
    )
    profile.default_model_alias = "default"
    save_profile(profile)
    return "realworld"


class TestAskEngagement:
    def test_ask_with_engagement_injects_system_message(
        self,
        tmp_engagement: Path,
        stub_transport: _StubTransport,
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
        stub_transport: _StubTransport,
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
        stub_transport: _StubTransport,
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
