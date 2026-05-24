"""D-065 — PII guard policy levels (off / warn / block / redact).

D-043 shipped the detector with two modes: warn (default) + off.
D-065 adds two more — ``block`` and ``redact`` — gated by the same
``PRAXIS_PII_GUARD`` env var. These tests pin behaviour per mode +
the end-to-end CLI integration on the ``ask`` and ``chat`` paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.safety import (
    PIIBlockedError,
    PIIGuardMode,
    PIIKind,
    apply_pii_policy,
    resolve_pii_guard_mode,
)

runner = CliRunner()


_SSN_INPUT = "My SSN is 123-45-6789 please advise."
_CC_INPUT = "Card 4111 1111 1111 1111 was charged."
_CLEAN_INPUT = "What's the project deadline?"


class TestModeResolution:
    @pytest.mark.parametrize(
        ("env", "expected"),
        [
            (None, PIIGuardMode.WARN),  # default
            ("", PIIGuardMode.WARN),
            ("warn", PIIGuardMode.WARN),
            ("WARN", PIIGuardMode.WARN),  # case-insensitive
            ("off", PIIGuardMode.OFF),
            ("OFF", PIIGuardMode.OFF),
            ("block", PIIGuardMode.BLOCK),
            ("redact", PIIGuardMode.REDACT),
            ("nonsense", PIIGuardMode.WARN),  # unknown → safe default
        ],
    )
    def test_env_var_resolution(
        self, env: str | None, expected: PIIGuardMode, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        if env is None:
            monkeypatch.delenv("PRAXIS_PII_GUARD", raising=False)
        else:
            monkeypatch.setenv("PRAXIS_PII_GUARD", env)
        assert resolve_pii_guard_mode() is expected


class TestApplyPolicyOff:
    def test_off_returns_input_unchanged_no_detection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "off")
        text, kinds = apply_pii_policy(_SSN_INPUT)
        assert text == _SSN_INPUT
        assert kinds == []


class TestApplyPolicyWarn:
    def test_warn_passes_input_through_and_reports_kinds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "warn")
        text, kinds = apply_pii_policy(_SSN_INPUT)
        assert text == _SSN_INPUT  # not modified
        assert PIIKind.SSN in kinds

    def test_warn_returns_empty_kinds_on_clean_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "warn")
        text, kinds = apply_pii_policy(_CLEAN_INPUT)
        assert text == _CLEAN_INPUT
        assert kinds == []


class TestApplyPolicyBlock:
    def test_block_raises_when_pii_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "block")
        with pytest.raises(PIIBlockedError) as excinfo:
            apply_pii_policy(_SSN_INPUT)
        assert PIIKind.SSN in excinfo.value.kinds
        # Error message names what to do next.
        msg = str(excinfo.value)
        assert "redact" in msg.lower()
        assert "ssn" in msg.lower()

    def test_block_passes_clean_input_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "block")
        text, kinds = apply_pii_policy(_CLEAN_INPUT)
        assert text == _CLEAN_INPUT
        assert kinds == []


class TestApplyPolicyRedact:
    def test_redact_replaces_ssn_with_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "redact")
        text, kinds = apply_pii_policy(_SSN_INPUT)
        assert "123-45-6789" not in text
        assert "[SSN]" in text
        assert PIIKind.SSN in kinds

    def test_redact_replaces_credit_card_with_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "redact")
        text, kinds = apply_pii_policy(_CC_INPUT)
        assert "4111 1111 1111 1111" not in text
        assert "4111-1111-1111-1111" not in text
        assert "[CC]" in text
        assert PIIKind.CREDIT_CARD in kinds

    def test_redact_preserves_surrounding_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "redact")
        text, _ = apply_pii_policy("Before 123-45-6789 after.")
        assert text == "Before [SSN] after."

    def test_redact_leaves_non_luhn_digit_runs_alone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A 13-digit number that fails Luhn must not be redacted as a card —
        this is a false-positive guard that was already pinned in D-043 and
        must still hold under the new mode."""
        monkeypatch.setenv("PRAXIS_PII_GUARD", "redact")
        text, kinds = apply_pii_policy("phone 1234567890123")  # not Luhn-valid
        assert text == "phone 1234567890123"
        assert kinds == []


# ---------------------------------------------------------------------------
# CLI integration — ask + chat must respect block/redact
# ---------------------------------------------------------------------------


class TestAskCommandPIIBlock:
    def test_block_mode_exits_nonzero_without_calling_llm(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_home: Path,
    ) -> None:
        """``praxis ask`` under PRAXIS_PII_GUARD=block must refuse to send.

        We monkeypatch ``make_transport`` to a tracker so we can assert
        the LLM was NEVER reached."""
        monkeypatch.setenv("PRAXIS_PII_GUARD", "block")

        # Need a default profile to even resolve the model_config.
        from praxis.config.loader import save_global_config, save_profile
        from praxis.config.models import GlobalConfig, ModelConfig, Provider
        from praxis.config.profiles import create_profile

        profile = create_profile("blocktest")
        profile.model_aliases["default"] = ModelConfig(
            provider=Provider.OPENAI, model="gpt-test", api_key_env="OPENAI_API_KEY"
        )
        profile.default_model_alias = "default"
        save_profile(profile)
        save_global_config(GlobalConfig(default_profile="blocktest"))

        transport_calls: list[object] = []

        def tracking_make_transport(_cfg: object) -> object:
            transport_calls.append(_cfg)
            raise AssertionError("LLM should never be reached under block mode")

        monkeypatch.setattr("praxis.cli.ask_cmd.make_transport", tracking_make_transport)

        result = runner.invoke(app, ["ask", _SSN_INPUT, "-p", "blocktest"])

        assert result.exit_code == 2, result.output
        assert transport_calls == [], "LLM was contacted under block mode"
        combined = result.output + (result.stderr or "")
        assert "block" in combined.lower()
        assert "ssn" in combined.lower()


class TestChatMessagePIIRedact:
    def test_redact_mode_replaces_pii_in_message_before_stream_turn(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_engagement: Path,
        tmp_home: Path,
    ) -> None:
        """``praxis chat -m`` under PRAXIS_PII_GUARD=redact must send the
        masked message to the runtime, not the original."""
        monkeypatch.setenv("PRAXIS_PII_GUARD", "redact")
        init_engagement(tmp_engagement, "Test")

        from types import SimpleNamespace

        from praxis.core.chat_runtime import ChatRuntime
        from praxis.core.models import StreamEvent

        captured: list[str] = []

        class _Fake:
            def __init__(self) -> None:
                self.engagement = SimpleNamespace(name="Test")

            def start(self) -> str:
                return "fake-sid"

            def stream_turn(self, text: str) -> object:
                captured.append(text)

                def _gen() -> object:
                    yield StreamEvent(type="text_delta", text="ok")
                    yield StreamEvent(type="done")

                return _gen()

            def close(self) -> None:
                pass

        fake = _Fake()
        monkeypatch.setattr(ChatRuntime, "create", classmethod(lambda cls, **kw: fake))

        message = "Member SSN 123-45-6789 — what's the policy?"
        result = runner.invoke(
            app,
            ["chat", "-m", message, "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0, result.output
        assert captured, "stream_turn was never called"
        assert "123-45-6789" not in captured[0], (
            f"redact mode failed to mask SSN before stream_turn; got {captured[0]!r}"
        )
        assert "[SSN]" in captured[0]
