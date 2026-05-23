"""D-050 — ``praxis chat --message/-m`` non-interactive single-turn mode.

Closes the scripting gap surfaced in the v0.3.0 workable-product
assessment: ``chat`` was REPL-only, so CI / one-shot agentic queries
that need the chat runtime (tools, session, slash commands) couldn't
use it. ``--message`` runs one turn through the same runtime and exits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.core.chat_runtime import ChatRuntime
from praxis.core.models import StreamEvent

runner = CliRunner()


class _FakeRuntime:
    """Test double for ChatRuntime — yields canned events without LLM calls."""

    def __init__(self, response: str = "hello back!") -> None:
        self._response = response
        self.start_calls = 0
        self.stream_inputs: list[str] = []
        self.closed = False

        class _Eng:
            name = "Test Engagement"

        self.engagement = _Eng()

    def start(self) -> str:
        self.start_calls += 1
        return "fake-session-id-abcdef0123"

    def stream_turn(self, user_input: str) -> Any:
        self.stream_inputs.append(user_input)
        yield StreamEvent(type="text_delta", text=self._response)
        yield StreamEvent(type="done")

    def close(self) -> None:
        self.closed = True


@pytest.fixture()
def fake_runtime(monkeypatch: pytest.MonkeyPatch) -> _FakeRuntime:
    """Replace ``ChatRuntime.create`` with a fake that returns a stub runtime."""
    instance = _FakeRuntime()

    def fake_create(cls: type[ChatRuntime], **kwargs: object) -> _FakeRuntime:
        return instance

    monkeypatch.setattr(ChatRuntime, "create", classmethod(fake_create))
    return instance


class TestChatMessage:
    def test_single_turn_exits_clean(
        self,
        fake_runtime: _FakeRuntime,
        tmp_engagement: Path,
        tmp_home: Path,
    ) -> None:
        """``chat -m "..."`` runs one turn, the runtime closes, exit 0."""
        init_engagement(tmp_engagement, "Test")

        result = runner.invoke(
            app,
            ["chat", "-m", "Hello agent", "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0, result.output
        assert fake_runtime.stream_inputs == ["Hello agent"]
        assert fake_runtime.closed is True
        assert "hello back!" in result.output

    def test_skips_repl_banner(
        self,
        fake_runtime: _FakeRuntime,
        tmp_engagement: Path,
        tmp_home: Path,
    ) -> None:
        """Non-interactive mode must NOT print the ``/help`` banner — it
        would corrupt stdout for callers piping into ``jq`` or similar."""
        init_engagement(tmp_engagement, "Test")

        result = runner.invoke(
            app,
            ["chat", "-m", "What's in scope?", "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0, result.output
        assert "/help for commands" not in result.output
        assert "Session ended" not in result.output

    def test_records_pii_warning(
        self,
        fake_runtime: _FakeRuntime,
        tmp_engagement: Path,
        tmp_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """PII detection must still fire on the single-turn input."""
        monkeypatch.delenv("PRAXIS_PII_GUARD", raising=False)
        init_engagement(tmp_engagement, "Test")

        result = runner.invoke(
            app,
            ["chat", "-m", "Member SSN is 123-45-6789", "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0
        combined = result.output + (result.stderr or "")
        assert "WARNING" in combined
        assert "ssn" in combined.lower()
        # Warn-only: the turn still went through.
        assert fake_runtime.stream_inputs == ["Member SSN is 123-45-6789"]

    def test_interactive_mode_still_works_when_no_message_supplied(
        self,
        fake_runtime: _FakeRuntime,
        tmp_engagement: Path,
        tmp_home: Path,
    ) -> None:
        """Regression: without ``--message``, the REPL path runs (and the
        banner appears). Use an empty stdin so the REPL exits on EOF
        without trying to call the LLM."""
        init_engagement(tmp_engagement, "Test")

        result = runner.invoke(
            app,
            ["chat", "-e", str(tmp_engagement)],
            input="",  # immediate EOF — REPL exits cleanly
        )

        assert result.exit_code == 0, result.output
        assert "/help for commands" in result.output
        assert "Session ended" in result.output
        assert fake_runtime.stream_inputs == []  # no turn was attempted
