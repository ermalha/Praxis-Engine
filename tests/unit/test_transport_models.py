"""Tests for transport models and base assembly logic."""

from __future__ import annotations

import threading

import pytest

from praxis.errors import TransportError
from praxis.transport import (
    StreamChunk,
    ToolCallDelta,
    Usage,
    assemble_response,
    assemble_tool_calls_from_stream,
)
from praxis.transport.base import _check_cancel


class TestAssembleResponse:
    def test_text_only(self) -> None:
        chunks = [
            StreamChunk(delta_text="Hello"),
            StreamChunk(delta_text=" world"),
            StreamChunk(finish_reason="stop"),
            StreamChunk(usage=Usage(prompt_tokens=5, completion_tokens=2)),
        ]
        resp = assemble_response(iter(chunks))
        assert resp.content == "Hello world"
        assert resp.finish_reason == "stop"
        assert resp.usage.prompt_tokens == 5
        assert resp.tool_calls is None

    def test_tool_call_assembly(self) -> None:
        chunks = [
            StreamChunk(tool_call_delta=ToolCallDelta(index=0, id="tc_1", name="search")),
            StreamChunk(tool_call_delta=ToolCallDelta(index=0, arguments_delta='{"q":')),
            StreamChunk(tool_call_delta=ToolCallDelta(index=0, arguments_delta=' "hello"}')),
            StreamChunk(finish_reason="tool_calls"),
        ]
        resp = assemble_response(iter(chunks))
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "search"
        assert resp.tool_calls[0].arguments_json == '{"q": "hello"}'

    def test_multiple_tool_calls(self) -> None:
        chunks = [
            StreamChunk(tool_call_delta=ToolCallDelta(index=0, id="tc_1", name="foo")),
            StreamChunk(tool_call_delta=ToolCallDelta(index=1, id="tc_2", name="bar")),
            StreamChunk(tool_call_delta=ToolCallDelta(index=0, arguments_delta='{"x": 1}')),
            StreamChunk(tool_call_delta=ToolCallDelta(index=1, arguments_delta='{"y": 2}')),
        ]
        resp = assemble_response(iter(chunks))
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 2
        assert resp.tool_calls[0].id == "tc_1"
        assert resp.tool_calls[1].id == "tc_2"

    def test_assemble_tool_calls_helper(self) -> None:
        chunks = [
            StreamChunk(tool_call_delta=ToolCallDelta(index=0, id="tc_1", name="fn")),
            StreamChunk(tool_call_delta=ToolCallDelta(index=0, arguments_delta='{"x": 1, "y": 2}')),
        ]
        tools = assemble_tool_calls_from_stream(chunks)
        assert len(tools) == 1
        assert tools[0].arguments_json == '{"x": 1, "y": 2}'


class TestCheckCancel:
    def test_not_set(self) -> None:
        event = threading.Event()
        _check_cancel(event)  # should not raise

    def test_set_raises(self) -> None:
        event = threading.Event()
        event.set()
        with pytest.raises(TransportError, match="interrupted"):
            _check_cancel(event)

    def test_none_is_noop(self) -> None:
        _check_cancel(None)  # should not raise
