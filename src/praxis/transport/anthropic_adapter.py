"""Anthropic Messages API transport adapter."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Iterator
from typing import Any

import structlog

from praxis.errors import TransportError
from praxis.transport.base import Transport, _check_cancel
from praxis.transport.models import (
    ChatRequest,
    ContentBlock,
    Message,
    ProbeResult,
    StreamChunk,
    ToolCallDelta,
    Usage,
)

logger = structlog.get_logger()


def _require_anthropic() -> type:
    """Lazily import the Anthropic SDK, raising a clear error if missing."""
    try:
        import anthropic

        return anthropic.Anthropic
    except ImportError:
        raise TransportError(
            "The 'anthropic' package is required for the Anthropic provider. "
            "Install it with: pip install praxis-ba[anthropic]",
            provider="anthropic",
        ) from None


class AnthropicTransport(Transport):
    """Adapter for the Anthropic Messages API."""

    name = "anthropic"

    def __init__(self, api_key_env: str, model: str, *, timeout_s: int = 120) -> None:
        self._api_key_env = api_key_env
        self._model = model
        self._timeout_s = timeout_s
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            api_key = os.environ.get(self._api_key_env)
            if not api_key:
                raise TransportError(
                    f"Environment variable {self._api_key_env} is not set",
                    provider="anthropic",
                    env_var=self._api_key_env,
                )
            cls = _require_anthropic()
            self._client = cls(api_key=api_key, timeout=self._timeout_s)
        return self._client

    def chat_stream(
        self,
        request: ChatRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion from the Anthropic Messages API."""
        client = self._get_client()
        params = self._build_params(request)

        try:
            with client.messages.stream(**params) as stream:
                for event in stream:
                    _check_cancel(cancel_event)
                    chunk = self._event_to_chunk(event)
                    if chunk is not None:
                        yield chunk

            # Final usage from the accumulated message
            final_message = stream.get_final_message()
            if final_message is not None:
                yield StreamChunk(
                    usage=Usage(
                        prompt_tokens=final_message.usage.input_tokens,
                        completion_tokens=final_message.usage.output_tokens,
                        cache_read_tokens=getattr(final_message.usage, "cache_read_input_tokens", 0)
                        or 0,
                        cache_write_tokens=getattr(
                            final_message.usage, "cache_creation_input_tokens", 0
                        )
                        or 0,
                    ),
                )
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError(f"Anthropic API error: {exc}", provider="anthropic") from exc

    def supports_tools(self) -> bool:
        return True

    def supports_caching(self) -> bool:
        return True

    def probe(self) -> ProbeResult:
        """Send a minimal request to verify connectivity."""
        start = time.monotonic()
        try:
            client = self._get_client()
            resp = client.messages.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            latency = (time.monotonic() - start) * 1000
            _ = resp  # ensure we got a response
            return ProbeResult(ok=True, provider="anthropic", model=self._model, latency_ms=latency)
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ProbeResult(
                ok=False,
                provider="anthropic",
                model=self._model,
                latency_ms=latency,
                error=str(exc),
            )

    def _build_params(self, request: ChatRequest) -> dict[str, object]:
        """Convert a ChatRequest to Anthropic API params."""
        system_msgs: list[str] = []
        api_messages: list[dict[str, object]] = []

        for i, msg in enumerate(request.messages):
            if msg.role == "system":
                text = msg.content if isinstance(msg.content, str) else _blocks_to_text(msg.content)
                system_msgs.append(text)
                continue

            content = self._convert_content(msg)
            api_msg: dict[str, object] = {"role": msg.role, "content": content}

            # Prompt caching: mark indicated messages
            if (
                request.cache_breakpoints
                and i in request.cache_breakpoints
                and isinstance(content, list)
            ):
                last_block = content[-1]
                if isinstance(last_block, dict):
                    last_block["cache_control"] = {"type": "ephemeral"}

            api_messages.append(api_msg)

        params: dict[str, object] = {
            "model": request.model,
            "messages": api_messages,
            "max_tokens": request.max_tokens or 4096,
        }

        if system_msgs:
            params["system"] = "\n\n".join(system_msgs)

        if request.temperature is not None:
            params["temperature"] = request.temperature

        if request.tools:
            params["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters_json_schema,
                }
                for t in request.tools
            ]

        if request.tool_choice:
            if request.tool_choice == "auto":
                params["tool_choice"] = {"type": "auto"}
            elif request.tool_choice == "none":
                params["tool_choice"] = {"type": "none"}
            else:
                params["tool_choice"] = {"type": "tool", "name": request.tool_choice}

        return params

    @staticmethod
    def _convert_content(msg: Message) -> str | list[dict[str, object]]:
        """Convert message content to Anthropic format."""
        if isinstance(msg.content, str):
            if msg.role == "assistant" and msg.tool_calls:
                blocks: list[dict[str, object]] = [{"type": "text", "text": msg.content}]
                for tc in msg.tool_calls:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": json.loads(tc.arguments_json),
                        }
                    )
                return blocks
            if msg.role == "tool":
                return [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id or "",
                        "content": msg.content,
                    }
                ]
            return msg.content

        blocks_out: list[dict[str, object]] = []
        for block in msg.content:
            if block.type == "text" and block.text:
                blocks_out.append({"type": "text", "text": block.text})
            elif block.type == "image" and block.image_base64:
                blocks_out.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": block.media_type or "image/png",
                            "data": block.image_base64,
                        },
                    }
                )
        return blocks_out

    @staticmethod
    def _event_to_chunk(event: object) -> StreamChunk | None:
        """Convert an Anthropic stream event to a StreamChunk."""
        event_type = getattr(event, "type", None)

        if event_type == "content_block_delta":
            delta = getattr(event, "delta", None)
            delta_type = getattr(delta, "type", None)
            if delta_type == "text_delta":
                return StreamChunk(delta_text=getattr(delta, "text", ""))
            if delta_type == "input_json_delta":
                return StreamChunk(
                    tool_call_delta=ToolCallDelta(
                        index=getattr(event, "index", 0),
                        arguments_delta=getattr(delta, "partial_json", ""),
                    )
                )
        elif event_type == "content_block_start":
            cb = getattr(event, "content_block", None)
            if getattr(cb, "type", None) == "tool_use":
                return StreamChunk(
                    tool_call_delta=ToolCallDelta(
                        index=getattr(event, "index", 0),
                        id=getattr(cb, "id", ""),
                        name=getattr(cb, "name", ""),
                    )
                )
        elif event_type == "message_delta":
            delta = getattr(event, "delta", None)
            stop_reason = getattr(delta, "stop_reason", None)
            if stop_reason:
                return StreamChunk(finish_reason=stop_reason)

        return None


def _blocks_to_text(blocks: list[ContentBlock]) -> str:
    """Extract text from content blocks."""
    return " ".join(b.text for b in blocks if b.text)
