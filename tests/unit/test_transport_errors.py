"""D-051 — Friendlier provider-error translation.

Closes the v0.2.0 NEW-003 finding plus the Hermes review's call for
more specific transport errors: today the OpenAI + Anthropic adapters
wrap every SDK exception in ``TransportError("... API call failed: {exc}")``,
which leaves the user guessing whether they hit auth / rate-limit /
network / wrong-model.

These tests cover the translation helper directly (so they don't depend
on real OpenAI / Anthropic SDK objects being installed) plus two
integration-style tests that route through the actual adapters using
duck-typed fake exception classes.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from praxis.errors import TransportError
from praxis.transport.errors import translate_provider_exception

# ---------------------------------------------------------------------------
# Fake SDK exceptions — keyed to live in modules whose names START with
# "openai" / "anthropic" so the translator's module-prefix check fires.
# ---------------------------------------------------------------------------


def _make_fake_exc(name: str, module: str, message: str = "boom") -> Exception:
    """Build an exception instance whose type name + module match a real SDK error."""
    cls = type(name, (Exception,), {"__module__": module})
    return cls(message)


class TestTranslateProviderException:
    @pytest.mark.parametrize(
        ("exc_name", "expected_kind", "expected_substr"),
        [
            ("AuthenticationError", "auth", "Authentication failed"),
            ("PermissionDeniedError", "permission", "Permission denied"),
            ("RateLimitError", "rate_limit", "Rate limit exceeded"),
            ("NotFoundError", "not_found", "Model 'gpt-4.1' not found"),
            ("BadRequestError", "bad_request", "Request rejected"),
            ("InternalServerError", "server_error", "server-side"),
            ("APIConnectionError", "connection", "Network error"),
            ("APITimeoutError", "timeout", "timed out"),
        ],
    )
    def test_openai_each_kind_translates(
        self, exc_name: str, expected_kind: str, expected_substr: str
    ) -> None:
        exc = _make_fake_exc(exc_name, module="openai.errors", message="upstream detail")
        err = translate_provider_exception(
            exc, provider="openai", model="gpt-4.1", api_key_env="OPENAI_API_KEY"
        )
        assert isinstance(err, TransportError)
        assert err.details["kind"] == expected_kind
        assert err.details["provider"] == "openai"
        assert expected_substr.lower() in str(err).lower()

    @pytest.mark.parametrize(
        ("exc_name", "expected_kind"),
        [
            ("AuthenticationError", "auth"),
            ("RateLimitError", "rate_limit"),
            ("APIConnectionError", "connection"),
        ],
    )
    def test_anthropic_each_kind_translates(self, exc_name: str, expected_kind: str) -> None:
        exc = _make_fake_exc(exc_name, module="anthropic.errors")
        err = translate_provider_exception(
            exc, provider="anthropic", model="claude-opus-4", api_key_env="ANTHROPIC_API_KEY"
        )
        assert err.details["kind"] == expected_kind
        assert err.details["provider"] == "anthropic"

    def test_auth_message_includes_env_var_name(self) -> None:
        """Auth errors must name the exact env var so users know what to set."""
        exc = _make_fake_exc("AuthenticationError", module="openai")
        err = translate_provider_exception(
            exc, provider="openai", model="gpt-4.1", api_key_env="MY_CUSTOM_KEY_VAR"
        )
        assert "MY_CUSTOM_KEY_VAR" in str(err)

    def test_unknown_exception_falls_through_to_generic(self) -> None:
        """Non-SDK exceptions (e.g. ValueError) keep today's generic message."""
        exc = ValueError("something weird")
        err = translate_provider_exception(exc, provider="openai", model="gpt-4.1")
        assert err.details["kind"] == "unknown"
        assert "API call failed" in str(err)
        assert "something weird" in str(err)

    def test_provider_title_is_capitalised_in_generic_message(self) -> None:
        """`{provider_title}` -> `Openai`, `Anthropic` — used in fallback + server_error."""
        exc = ValueError("oops")
        err = translate_provider_exception(exc, provider="anthropic")
        assert "Anthropic API call failed" in str(err)


# ---------------------------------------------------------------------------
# Integration-style: route the translator through the live adapter code path.
# ---------------------------------------------------------------------------


class TestOpenAIAdapterUsesTranslator:
    def test_auth_error_propagates_through_chat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        exc = _make_fake_exc("AuthenticationError", module="openai", message="401 Unauthorized")

        class FakeCompletions:
            def create(self, **kwargs: object) -> object:
                raise exc

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                self.chat = FakeChat()

        with patch(
            "praxis.transport.openai_adapter._require_openai",
            return_value=FakeClient,
        ):
            from praxis.transport.models import ChatRequest, Message
            from praxis.transport.openai_adapter import OpenAITransport

            transport = OpenAITransport(api_key_env="OPENAI_API_KEY", model="gpt-test")
            request = ChatRequest(model="gpt-test", messages=[Message(role="user", content="hi")])

            with pytest.raises(TransportError) as exc_info:
                list(transport.chat_stream(request))

            assert exc_info.value.details["kind"] == "auth"
            assert "Authentication failed" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)


class TestAnthropicAdapterUsesTranslator:
    def test_rate_limit_propagates_through_chat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        exc = _make_fake_exc("RateLimitError", module="anthropic", message="429 Too Many Requests")

        class FakeMessages:
            def stream(self, **kwargs: object) -> object:
                raise exc

            def create(self, **kwargs: object) -> object:
                raise exc

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                self.messages = FakeMessages()

        with patch(
            "praxis.transport.anthropic_adapter._require_anthropic",
            return_value=FakeClient,
        ):
            from praxis.transport.anthropic_adapter import AnthropicTransport
            from praxis.transport.models import ChatRequest, Message

            transport = AnthropicTransport(api_key_env="ANTHROPIC_API_KEY", model="claude-test")
            request = ChatRequest(
                model="claude-test", messages=[Message(role="user", content="hi")]
            )

            with pytest.raises(TransportError) as exc_info:
                list(transport.chat_stream(request))

            assert exc_info.value.details["kind"] == "rate_limit"
            assert "Rate limit exceeded" in str(exc_info.value)
