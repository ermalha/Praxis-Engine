"""Tests for transport adapters using respx mocks."""

from __future__ import annotations

import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

from praxis.config.models import ModelConfig, Provider
from praxis.errors import TransportError
from praxis.transport import (
    ChatRequest,
    Message,
    ToolDefinition,
    make_transport,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_request(model: str = "test-model") -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=[Message(role="user", content="say pong")],
    )


def _tool_request(model: str = "test-model") -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=[Message(role="user", content="search for hello")],
        tools=[
            ToolDefinition(
                name="search",
                description="Search for something",
                parameters_json_schema={
                    "type": "object",
                    "properties": {"q": {"type": "string"}},
                },
            )
        ],
    )


# ---------------------------------------------------------------------------
# Anthropic adapter
# ---------------------------------------------------------------------------


class TestAnthropicAdapter:
    def test_request_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify Anthropic adapter formats the request correctly."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        captured: dict[str, object] = {}

        class FakeStream:
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)
                self._events: list[object] = [
                    _make_anthropic_text_event("pong"),
                    _make_anthropic_stop_event(),
                ]
                self._final = _make_anthropic_final_message(5, 1)

            def __enter__(self) -> FakeStream:
                return self

            def __exit__(self, *a: object) -> None:
                pass

            def __iter__(self) -> FakeStream:
                return self

            def __next__(self) -> object:
                if not self._events:
                    raise StopIteration
                return self._events.pop(0)

            def get_final_message(self) -> object:
                return self._final

        class FakeMessages:
            def stream(self, **kwargs: object) -> FakeStream:
                return FakeStream(**kwargs)

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                self.messages = FakeMessages()

        with patch(
            "praxis.transport.anthropic_adapter._require_anthropic",
            return_value=FakeClient,
        ):
            from praxis.transport.anthropic_adapter import AnthropicTransport

            transport = AnthropicTransport(api_key_env="ANTHROPIC_API_KEY", model="claude-test")
            response = transport.chat(_simple_request("claude-test"))

        assert response.content == "pong"
        assert captured["model"] == "claude-test"
        assert captured["max_tokens"] == 4096
        assert len(captured["messages"]) == 1  # type: ignore[arg-type]

    def test_tool_call_streaming(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        class FakeStream:
            def __init__(self, **kwargs: object) -> None:
                self._events = [
                    _make_anthropic_tool_start(0, "tc_1", "search"),
                    _make_anthropic_tool_delta(0, '{"q": "hello"}'),
                    _make_anthropic_stop_event("tool_use"),
                ]
                self._final = _make_anthropic_final_message(10, 5)

            def __enter__(self) -> FakeStream:
                return self

            def __exit__(self, *a: object) -> None:
                pass

            def __iter__(self) -> FakeStream:
                return self

            def __next__(self) -> object:
                if not self._events:
                    raise StopIteration
                return self._events.pop(0)

            def get_final_message(self) -> object:
                return self._final

        class FakeMessages:
            def stream(self, **kwargs: object) -> FakeStream:
                return FakeStream(**kwargs)

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                self.messages = FakeMessages()

        with patch(
            "praxis.transport.anthropic_adapter._require_anthropic",
            return_value=FakeClient,
        ):
            from praxis.transport.anthropic_adapter import AnthropicTransport

            transport = AnthropicTransport(api_key_env="ANTHROPIC_API_KEY", model="claude-test")
            response = transport.chat(_tool_request("claude-test"))

        assert response.tool_calls is not None
        assert response.tool_calls[0].name == "search"
        assert response.tool_calls[0].arguments_json == '{"q": "hello"}'

    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                pass

        with patch(
            "praxis.transport.anthropic_adapter._require_anthropic",
            return_value=FakeClient,
        ):
            from praxis.transport.anthropic_adapter import AnthropicTransport

            transport = AnthropicTransport(api_key_env="ANTHROPIC_API_KEY", model="claude-test")
            with pytest.raises(TransportError, match="ANTHROPIC_API_KEY"):
                transport.chat(_simple_request())

    def test_supports_tools_and_caching(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                pass

        with patch(
            "praxis.transport.anthropic_adapter._require_anthropic",
            return_value=FakeClient,
        ):
            from praxis.transport.anthropic_adapter import AnthropicTransport

            transport = AnthropicTransport(api_key_env="ANTHROPIC_API_KEY", model="claude-test")
            assert transport.supports_tools() is True
            assert transport.supports_caching() is True


# ---------------------------------------------------------------------------
# OpenAI adapter
# ---------------------------------------------------------------------------


class TestOpenAIAdapter:
    def test_request_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        captured: dict[str, object] = {}

        class FakeCompletions:
            def create(self, **kwargs: object) -> list[object]:
                captured.update(kwargs)
                return [_make_openai_chunk("pong", finish_reason="stop")]

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                self.chat = FakeChat()

        with patch(
            "praxis.transport.openai_adapter._require_openai",
            return_value=FakeClient,
        ):
            from praxis.transport.openai_adapter import OpenAITransport

            transport = OpenAITransport(api_key_env="OPENAI_API_KEY", model="gpt-test")
            response = transport.chat(_simple_request("gpt-test"))

        assert response.content == "pong"
        assert captured["model"] == "gpt-test"

    def test_tool_call_streaming(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        class FakeCompletions:
            def create(self, **kwargs: object) -> list[object]:
                return [
                    _make_openai_tool_chunk(0, "tc_1", "search", '{"q":'),
                    _make_openai_tool_chunk(0, None, None, ' "hello"}'),
                    _make_openai_chunk(None, finish_reason="tool_calls"),
                    _make_openai_usage_chunk(10, 5),
                ]

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                self.chat = FakeChat()

        with patch(
            "praxis.transport.openai_adapter._require_openai",
            return_value=FakeClient,
        ):
            from praxis.transport.openai_adapter import OpenAITransport

            transport = OpenAITransport(api_key_env="OPENAI_API_KEY", model="gpt-test")
            response = transport.chat(_tool_request("gpt-test"))

        assert response.tool_calls is not None
        assert response.tool_calls[0].name == "search"
        assert response.tool_calls[0].arguments_json == '{"q": "hello"}'

    def test_interruption(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        class FakeCompletions:
            def create(self, **kwargs: object) -> list[object]:
                return [
                    _make_openai_chunk("first"),
                    _make_openai_chunk("second"),
                    _make_openai_chunk("third"),
                ]

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                self.chat = FakeChat()

        with patch(
            "praxis.transport.openai_adapter._require_openai",
            return_value=FakeClient,
        ):
            from praxis.transport.openai_adapter import OpenAITransport

            transport = OpenAITransport(api_key_env="OPENAI_API_KEY", model="gpt-test")
            cancel = threading.Event()
            iterator = transport.chat_stream(_simple_request("gpt-test"), cancel_event=cancel)
            # Get first chunk
            first = next(iterator)
            assert first.delta_text == "first"
            # Set cancel
            cancel.set()
            with pytest.raises(TransportError) as exc_info:
                list(iterator)
            assert exc_info.value.details.get("interrupted") is True

    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                pass

        with patch(
            "praxis.transport.openai_adapter._require_openai",
            return_value=FakeClient,
        ):
            from praxis.transport.openai_adapter import OpenAITransport

            transport = OpenAITransport(api_key_env="OPENAI_API_KEY", model="gpt-test")
            with pytest.raises(TransportError, match="OPENAI_API_KEY"):
                transport.chat(_simple_request())


# ---------------------------------------------------------------------------
# OpenRouter adapter
# ---------------------------------------------------------------------------


class TestOpenRouterAdapter:
    def test_extra_headers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

        captured_headers: dict[str, str] = {}

        class FakeCompletions:
            def create(self, **kwargs: object) -> list[object]:
                return [_make_openai_chunk("ok", finish_reason="stop")]

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                captured_headers.update(kwargs.get("default_headers", {}))  # type: ignore[arg-type]
                self.chat = FakeChat()

        with patch(
            "praxis.transport.openai_adapter._require_openai",
            return_value=FakeClient,
        ):
            from praxis.transport.openrouter_adapter import OpenRouterTransport

            transport = OpenRouterTransport(api_key_env="OPENROUTER_API_KEY", model="test/model")
            transport.chat(_simple_request("test/model"))

        assert "HTTP-Referer" in captured_headers
        assert "X-Title" in captured_headers


# ---------------------------------------------------------------------------
# Compat adapter
# ---------------------------------------------------------------------------


class TestCompatAdapter:
    def test_tools_not_supported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOCAL_API_KEY", "test-key")

        class FakeClient:
            def __init__(self, **kwargs: object) -> None:
                pass

        with patch(
            "praxis.transport.openai_adapter._require_openai",
            return_value=FakeClient,
        ):
            from praxis.transport.compat_adapter import CompatTransport

            transport = CompatTransport(
                api_key_env="LOCAL_API_KEY",
                model="local-model",
                base_url="http://localhost:11434/v1",
            )
            assert transport.supports_tools() is False
            assert transport.supports_caching() is False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    def test_anthropic_factory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        config = ModelConfig(
            provider=Provider.ANTHROPIC,
            model="claude-test",
            api_key_env="ANTHROPIC_API_KEY",
        )
        transport = make_transport(config)
        assert transport.name == "anthropic"

    def test_openai_factory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        config = ModelConfig(
            provider=Provider.OPENAI,
            model="gpt-test",
            api_key_env="OPENAI_API_KEY",
        )
        transport = make_transport(config)
        assert transport.name == "openai"

    def test_openrouter_factory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        config = ModelConfig(
            provider=Provider.OPENROUTER,
            model="test/model",
            api_key_env="OPENROUTER_API_KEY",
        )
        transport = make_transport(config)
        assert transport.name == "openrouter"

    def test_compat_factory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOCAL_KEY", "test-key")
        config = ModelConfig(
            provider=Provider.OPENAI_COMPAT,
            model="local-model",
            api_key_env="LOCAL_KEY",
            base_url="http://localhost:11434/v1",
        )
        transport = make_transport(config)
        assert transport.name == "openai_compat"

    def test_compat_requires_base_url(self) -> None:
        config = ModelConfig(
            provider=Provider.OPENAI_COMPAT,
            model="local-model",
            api_key_env="LOCAL_KEY",
        )
        with pytest.raises(TransportError, match="base_url"):
            make_transport(config)

    def test_missing_anthropic_dep(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setitem(sys.modules, "anthropic", None)
        config = ModelConfig(
            provider=Provider.ANTHROPIC,
            model="claude-test",
            api_key_env="ANTHROPIC_API_KEY",
        )
        transport = make_transport(config)
        with pytest.raises(TransportError, match="anthropic"):
            transport.chat(_simple_request())

    def test_missing_openai_dep(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setitem(sys.modules, "openai", None)
        config = ModelConfig(
            provider=Provider.OPENAI,
            model="gpt-test",
            api_key_env="OPENAI_API_KEY",
        )
        transport = make_transport(config)
        with pytest.raises(TransportError, match="openai"):
            transport.chat(_simple_request())


# ---------------------------------------------------------------------------
# Fake event helpers
# ---------------------------------------------------------------------------


def _make_anthropic_text_event(text: str) -> object:
    ev = MagicMock()
    ev.type = "content_block_delta"
    ev.delta.type = "text_delta"
    ev.delta.text = text
    ev.index = 0
    return ev


def _make_anthropic_stop_event(reason: str = "end_turn") -> object:
    ev = MagicMock()
    ev.type = "message_delta"
    ev.delta.stop_reason = reason
    return ev


def _make_anthropic_tool_start(index: int, tc_id: str, name: str) -> object:
    ev = MagicMock()
    ev.type = "content_block_start"
    ev.index = index
    ev.content_block.type = "tool_use"
    ev.content_block.id = tc_id
    ev.content_block.name = name
    return ev


def _make_anthropic_tool_delta(index: int, partial_json: str) -> object:
    ev = MagicMock()
    ev.type = "content_block_delta"
    ev.index = index
    ev.delta.type = "input_json_delta"
    ev.delta.partial_json = partial_json
    return ev


def _make_anthropic_final_message(input_tokens: int, output_tokens: int) -> object:
    msg = MagicMock()
    msg.usage.input_tokens = input_tokens
    msg.usage.output_tokens = output_tokens
    msg.usage.cache_read_input_tokens = 0
    msg.usage.cache_creation_input_tokens = 0
    return msg


def _make_openai_chunk(text: str | None, *, finish_reason: str | None = None) -> object:
    chunk = MagicMock()
    choice = MagicMock()
    choice.delta.content = text
    choice.delta.tool_calls = None
    choice.finish_reason = finish_reason
    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _make_openai_tool_chunk(
    index: int,
    tc_id: str | None,
    name: str | None,
    arguments: str | None,
) -> object:
    chunk = MagicMock()
    choice = MagicMock()
    choice.delta.content = None
    tc = MagicMock()
    tc.index = index
    tc.id = tc_id
    tc.function.name = name
    tc.function.arguments = arguments
    choice.delta.tool_calls = [tc]
    choice.finish_reason = None
    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _make_openai_usage_chunk(prompt_tokens: int, completion_tokens: int) -> object:
    chunk = MagicMock()
    chunk.choices = []
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.prompt_tokens_details = None
    chunk.usage = usage
    return chunk
