"""Integration test for `ask` PII warning behavior (D-043).

Closes RW-018. `ask` sent raw user input straight to the LLM provider
with no warning even when the input contained an SSN. Now emits a
stderr warning before the call; never blocks. Setting
``PRAXIS_PII_GUARD=off`` silences the warning.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from praxis.cli import app

from .conftest import StubTransport

runner = CliRunner()


class TestAskPIIWarning:
    def test_ssn_in_prompt_emits_warning_and_calls_llm(
        self,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("PRAXIS_PII_GUARD", raising=False)

        result = runner.invoke(
            app,
            ["ask", "-p", realworld_profile, "The SSN is 123-45-6789, please advise."],
        )

        assert result.exit_code == 0, result.output
        # Warning should appear in stderr (or combined output).
        combined = result.output + (result.stderr if result.stderr else "")
        assert "WARNING" in combined
        assert "ssn" in combined.lower()
        # And the LLM call should still have happened (warn-only, never blocks).
        assert len(stub_transport.requests) == 1

    def test_pii_guard_off_silences_warning(
        self,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("PRAXIS_PII_GUARD", "off")

        result = runner.invoke(
            app,
            ["ask", "-p", realworld_profile, "The SSN is 123-45-6789, please advise."],
        )

        assert result.exit_code == 0, result.output
        combined = result.output + (result.stderr if result.stderr else "")
        assert "WARNING" not in combined
        # LLM still called.
        assert len(stub_transport.requests) == 1

    def test_clean_input_emits_no_warning(
        self,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("PRAXIS_PII_GUARD", raising=False)

        result = runner.invoke(
            app,
            ["ask", "-p", realworld_profile, "What's the MVP scope?"],
        )

        assert result.exit_code == 0, result.output
        combined = result.output + (result.stderr if result.stderr else "")
        assert "WARNING" not in combined
