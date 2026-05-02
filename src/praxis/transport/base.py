"""Abstract base class for LLM transport adapters."""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from collections.abc import Iterator

from praxis.transport.models import (
    ChatRequest,
    ChatResponse,
    ProbeResult,
    StreamChunk,
    ToolCall,
    Usage,
)


class Transport(ABC):
    """Provider-agnostic interface for LLM communication."""

    name: str

    @abstractmethod
    def chat_stream(
        self,
        request: ChatRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion, yielding chunks."""

    def chat(
        self,
        request: ChatRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> ChatResponse:
        """Non-streaming chat completion (consumes ``chat_stream``)."""
        return assemble_response(self.chat_stream(request, cancel_event=cancel_event))

    @abstractmethod
    def supports_tools(self) -> bool:
        """Whether this transport supports tool/function calling."""

    @abstractmethod
    def supports_caching(self) -> bool:
        """Whether this transport supports prompt caching."""

    @abstractmethod
    def probe(self) -> ProbeResult:
        """Run a minimal health check against the provider."""


def assemble_response(chunks: Iterator[StreamChunk]) -> ChatResponse:
    """Assemble a full ``ChatResponse`` from a stream of chunks."""
    text_parts: list[str] = []
    tool_calls_by_index: dict[int, dict[str, str]] = {}
    finish_reason = "stop"
    usage = Usage()

    for chunk in chunks:
        if chunk.delta_text:
            text_parts.append(chunk.delta_text)

        if chunk.tool_call_delta:
            delta = chunk.tool_call_delta
            idx = delta.index
            if idx not in tool_calls_by_index:
                tool_calls_by_index[idx] = {"id": "", "name": "", "arguments": ""}
            entry = tool_calls_by_index[idx]
            if delta.id:
                entry["id"] = delta.id
            if delta.name:
                entry["name"] = delta.name
            if delta.arguments_delta:
                entry["arguments"] += delta.arguments_delta

        if chunk.finish_reason:
            finish_reason = chunk.finish_reason
        if chunk.usage:
            usage = chunk.usage

    assembled_tool_calls: list[ToolCall] | None = None
    if tool_calls_by_index:
        assembled_tool_calls = [
            ToolCall(
                id=entry["id"],
                name=entry["name"],
                arguments_json=entry["arguments"],
            )
            for _, entry in sorted(tool_calls_by_index.items())
        ]

    return ChatResponse(
        content="".join(text_parts),
        tool_calls=assembled_tool_calls,
        finish_reason=finish_reason,
        usage=usage,
    )


def assemble_tool_calls_from_stream(chunks: list[StreamChunk]) -> list[ToolCall]:
    """Convenience: extract assembled tool calls from a list of chunks."""
    response = assemble_response(iter(chunks))
    return response.tool_calls or []


def _check_cancel(cancel_event: threading.Event | None) -> None:
    """Raise if the cancel event is set."""
    if cancel_event is not None and cancel_event.is_set():
        from praxis.errors import TransportError

        raise TransportError("Request interrupted", interrupted=True)


def _safe_json_parse(text: str) -> object:
    """Parse JSON, returning the raw string on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
