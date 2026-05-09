"""OpenAI Chat Completions API transport adapter."""

from __future__ import annotations

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
    Message,
    ProbeResult,
    StreamChunk,
    ToolCallDelta,
    Usage,
)

logger = structlog.get_logger()


def _require_openai() -> type:
    """Lazily import the OpenAI SDK, raising a clear error if missing."""
    try:
        import openai

        return openai.OpenAI
    except ImportError:
        raise TransportError(
            "The 'openai' package is required for the OpenAI provider. "
            "Install it with: pip install praxis-ba[openai]",
            provider="openai",
        ) from None


class OpenAITransport(Transport):
    """Adapter for the OpenAI Chat Completions API."""

    name = "openai"

    def __init__(
        self,
        api_key_env: str,
        model: str,
        *,
        base_url: str | None = None,
        timeout_s: int = 120,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._api_key_env = api_key_env
        self._model = model
        self._base_url = base_url
        self._timeout_s = timeout_s
        self._extra_headers = extra_headers or {}
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            api_key = os.environ.get(self._api_key_env)
            if not api_key:
                raise TransportError(
                    f"Environment variable {self._api_key_env} is not set",
                    provider=self.name,
                    env_var=self._api_key_env,
                )
            cls = _require_openai()
            kwargs: dict[str, object] = {
                "api_key": api_key,
                "timeout": float(self._timeout_s),
            }
            if self._base_url:
                kwargs["base_url"] = self._base_url
            if self._extra_headers:
                kwargs["default_headers"] = self._extra_headers
            self._client = cls(**kwargs)
        return self._client

    def chat_stream(
        self,
        request: ChatRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion from the OpenAI API."""
        client = self._get_client()
        params = self._build_params(request)
        params["stream"] = True
        params["stream_options"] = {"include_usage": True}

        try:
            response = client.chat.completions.create(**params)
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError(f"OpenAI API call failed: {exc}", provider=self.name) from exc
        try:
            for chunk in response:
                _check_cancel(cancel_event)
                result = self._chunk_to_stream_chunk(chunk)
                if result is not None:
                    yield result
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError(f"OpenAI stream error: {exc}", provider=self.name) from exc
        finally:
            if hasattr(response, "close"):
                response.close()

    def supports_tools(self) -> bool:
        return True

    def supports_caching(self) -> bool:
        return False

    def probe(self) -> ProbeResult:
        """Send a minimal request to verify connectivity."""
        start = time.monotonic()
        try:
            client = self._get_client()
            resp = client.chat.completions.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            latency = (time.monotonic() - start) * 1000
            _ = resp
            return ProbeResult(ok=True, provider=self.name, model=self._model, latency_ms=latency)
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ProbeResult(
                ok=False,
                provider=self.name,
                model=self._model,
                latency_ms=latency,
                error=str(exc),
            )

    def _build_params(self, request: ChatRequest) -> dict[str, object]:
        """Convert a ChatRequest to OpenAI API params."""
        messages: list[dict[str, object]] = []
        for msg in request.messages:
            messages.append(self._convert_message(msg))

        params: dict[str, object] = {
            "model": request.model,
            "messages": messages,
        }

        if request.max_tokens is not None:
            params["max_tokens"] = request.max_tokens

        if request.temperature is not None:
            params["temperature"] = request.temperature

        if request.tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters_json_schema,
                    },
                }
                for t in request.tools
            ]

        if request.tool_choice:
            if request.tool_choice in ("auto", "none"):
                params["tool_choice"] = request.tool_choice
            else:
                params["tool_choice"] = {
                    "type": "function",
                    "function": {"name": request.tool_choice},
                }

        return params

    @staticmethod
    def _convert_message(msg: Message) -> dict[str, object]:
        """Convert a Message to OpenAI format."""
        result: dict[str, object] = {"role": msg.role}

        if isinstance(msg.content, str):
            result["content"] = msg.content
        else:
            parts: list[dict[str, object]] = []
            for block in msg.content:
                if block.type == "text" and block.text:
                    parts.append({"type": "text", "text": block.text})
                elif block.type == "image" and block.image_base64:
                    parts.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{block.media_type or 'image/png'};base64,"
                                f"{block.image_base64}"
                            },
                        }
                    )
            result["content"] = parts

        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments_json},
                }
                for tc in msg.tool_calls
            ]

        if msg.tool_call_id:
            result["tool_call_id"] = msg.tool_call_id

        if msg.name:
            result["name"] = msg.name

        return result

    @staticmethod
    def _chunk_to_stream_chunk(chunk: object) -> StreamChunk | None:
        """Convert an OpenAI stream chunk to a StreamChunk."""
        choices = getattr(chunk, "choices", None)
        usage_data = getattr(chunk, "usage", None)

        # Usage-only final chunk
        if not choices and usage_data:
            return StreamChunk(
                usage=Usage(
                    prompt_tokens=getattr(usage_data, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage_data, "completion_tokens", 0) or 0,
                    cache_read_tokens=getattr(usage_data, "prompt_tokens_details", None)
                    and getattr(usage_data.prompt_tokens_details, "cached_tokens", 0)
                    or 0,
                    cache_write_tokens=0,
                ),
            )

        if not choices:
            return None

        choice = choices[0]
        delta = getattr(choice, "delta", None)
        if delta is None:
            return None

        result = StreamChunk()
        text = getattr(delta, "content", None)
        if text:
            result = StreamChunk(delta_text=text)

        tool_calls = getattr(delta, "tool_calls", None)
        if tool_calls:
            tc = tool_calls[0]
            func = getattr(tc, "function", None)
            result = StreamChunk(
                delta_text=text,
                tool_call_delta=ToolCallDelta(
                    index=getattr(tc, "index", 0) or 0,
                    id=getattr(tc, "id", None),
                    name=getattr(func, "name", None) if func else None,
                    arguments_delta=getattr(func, "arguments", None) if func else None,
                ),
            )

        finish = getattr(choice, "finish_reason", None)
        if finish:
            result = StreamChunk(
                delta_text=result.delta_text,
                tool_call_delta=result.tool_call_delta,
                finish_reason=finish,
            )

        # Check for usage in chunk
        if usage_data:
            result = StreamChunk(
                delta_text=result.delta_text,
                tool_call_delta=result.tool_call_delta,
                finish_reason=result.finish_reason,
                usage=Usage(
                    prompt_tokens=getattr(usage_data, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage_data, "completion_tokens", 0) or 0,
                ),
            )

        # Don't yield empty chunks
        if (
            result.delta_text is None
            and result.tool_call_delta is None
            and result.finish_reason is None
            and result.usage is None
        ):
            return None

        return result
