"""Chunk 04 acceptance test — transport layer end-to-end."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.models import ModelConfig, Provider
from praxis.errors import TransportError
from praxis.transport import (
    ChatRequest,
    Message,
    StreamChunk,
    ToolCallDelta,
    assemble_tool_calls_from_stream,
    make_transport,
)

runner = CliRunner()


def test_anthropic_roundtrip_via_ask(tmp_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """praxis ask against a mocked Anthropic adapter returns expected text."""
    # Set up a profile with an Anthropic model
    from praxis.config.loader import save_profile
    from praxis.config.profiles import create_profile

    prof = create_profile("default")
    prof.model_aliases = {
        "default": ModelConfig(
            provider=Provider.ANTHROPIC,
            model="claude-test",
            api_key_env="ANTHROPIC_API_KEY",
        )
    }
    save_profile(prof)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    # Mock the Anthropic SDK
    class FakeStream:
        def __init__(self, **kwargs: object) -> None:
            self._events = [_make_text_event("pong"), _make_stop_event()]
            self._final = _make_final_msg(5, 1)

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
        result = runner.invoke(app, ["ask", "say pong"])

    assert result.exit_code == 0
    assert "pong" in result.stdout


def test_streaming_with_tool_calls() -> None:
    """Tool call arguments assembled correctly across stream chunks."""
    chunks = [
        StreamChunk(tool_call_delta=ToolCallDelta(index=0, id="tc_1", name="search")),
        StreamChunk(tool_call_delta=ToolCallDelta(index=0, arguments_delta='{"x":')),
        StreamChunk(tool_call_delta=ToolCallDelta(index=0, arguments_delta=" 1, ")),
        StreamChunk(tool_call_delta=ToolCallDelta(index=0, arguments_delta='"y": 2}')),
        StreamChunk(finish_reason="tool_calls"),
    ]
    assembled = assemble_tool_calls_from_stream(chunks)
    assert len(assembled) == 1
    assert assembled[0].arguments_json == '{"x": 1, "y": 2}'


def test_interruption(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cancel event aborts mid-stream with TransportError(interrupted=True)."""
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
        iterator = transport.chat_stream(
            ChatRequest(
                model="gpt-test",
                messages=[Message(role="user", content="test")],
            ),
            cancel_event=cancel,
        )
        # Get first chunk
        next(iterator)
        # Cancel mid-stream
        cancel.set()
        with pytest.raises(TransportError) as exc_info:
            list(iterator)
        assert exc_info.value.details.get("interrupted") is True


def test_provider_factory_missing_dep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing SDK raises clear TransportError with install hint."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "anthropic", None)
    config = ModelConfig(
        provider=Provider.ANTHROPIC,
        model="claude-test",
        api_key_env="ANTHROPIC_API_KEY",
    )
    transport = make_transport(config)
    with pytest.raises(TransportError, match="install.*anthropic"):
        transport.chat(
            ChatRequest(
                model="claude-test",
                messages=[Message(role="user", content="hi")],
            )
        )


# ---------------------------------------------------------------------------
# Helpers for fake Anthropic events
# ---------------------------------------------------------------------------


def _make_text_event(text: str) -> object:
    ev = MagicMock()
    ev.type = "content_block_delta"
    ev.delta.type = "text_delta"
    ev.delta.text = text
    ev.index = 0
    return ev


def _make_stop_event() -> object:
    ev = MagicMock()
    ev.type = "message_delta"
    ev.delta.stop_reason = "end_turn"
    return ev


def _make_final_msg(input_tokens: int, output_tokens: int) -> object:
    msg = MagicMock()
    msg.usage.input_tokens = input_tokens
    msg.usage.output_tokens = output_tokens
    msg.usage.cache_read_input_tokens = 0
    msg.usage.cache_creation_input_tokens = 0
    return msg


def _make_openai_chunk(text: str | None) -> object:
    chunk = MagicMock()
    choice = MagicMock()
    choice.delta.content = text
    choice.delta.tool_calls = None
    choice.finish_reason = None
    chunk.choices = [choice]
    chunk.usage = None
    return chunk
