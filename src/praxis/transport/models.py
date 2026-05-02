"""Provider-neutral request/response types for LLM transport.

Internal format follows OpenAI-style conventions (easiest to translate from).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ContentBlock(BaseModel):
    """A single content block — text or image."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text", "image"] = "text"
    text: str | None = None
    image_base64: str | None = None
    media_type: str | None = None


class ToolDefinition(BaseModel):
    """JSON Schema definition of a tool the model may call."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters_json_schema: dict[str, object]


class ToolCall(BaseModel):
    """A tool invocation returned by the model."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    arguments_json: str


class Message(BaseModel):
    """A single message in a conversation."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[ContentBlock]
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None


class Usage(BaseModel):
    """Token usage statistics."""

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class ChatRequest(BaseModel):
    """Provider-neutral chat completion request."""

    model_config = ConfigDict(extra="forbid")

    model: str
    messages: list[Message]
    tools: list[ToolDefinition] | None = None
    tool_choice: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    cache_breakpoints: list[int] | None = None


class ChatResponse(BaseModel):
    """Provider-neutral chat completion response."""

    model_config = ConfigDict(extra="forbid")

    content: str = ""
    tool_calls: list[ToolCall] | None = None
    finish_reason: str = "stop"
    usage: Usage = Usage()


class StreamChunk(BaseModel):
    """A single chunk from a streaming response."""

    model_config = ConfigDict(extra="forbid")

    delta_text: str | None = None
    tool_call_delta: ToolCallDelta | None = None
    finish_reason: str | None = None
    usage: Usage | None = None


class ToolCallDelta(BaseModel):
    """Partial tool call data from a stream chunk."""

    model_config = ConfigDict(extra="forbid")

    index: int = 0
    id: str | None = None
    name: str | None = None
    arguments_delta: str | None = None


class ProbeResult(BaseModel):
    """Result of a connectivity health check."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    provider: str
    model: str
    latency_ms: float = 0.0
    error: str | None = None


# Rebuild forward refs (StreamChunk references ToolCallDelta)
StreamChunk.model_rebuild()
