# Chunk 04 — LLM Transport Layer

**Phase:** Foundations | **Estimated effort:** 5–6 hours | **Dependencies:** 01, 02

---

## Context

Praxis must be **provider-agnostic** (P11). The agent code calls a single
`Transport` interface; concrete adapters handle Anthropic, OpenAI, OpenRouter,
and OpenAI-compatible local servers (Ollama, vLLM, LM Studio, etc.).

This chunk delivers a clean abstraction with at least four adapters, supports
streaming, supports tool/function calling at the protocol level, supports
prompt caching where the provider does, and supports interruption mid-call.

---

## Scope

### Public API (`src/praxis/transport/__init__.py`)

```python
class Transport(ABC):
    name: str

    def chat(self, request: ChatRequest) -> ChatResponse: ...
    def chat_stream(self, request: ChatRequest) -> Iterator[StreamChunk]: ...
    def supports_tools(self) -> bool: ...
    def supports_caching(self) -> bool: ...

def make_transport(model_config: ModelConfig) -> Transport: ...
```

### Internal types (`src/praxis/transport/models.py`)

Provider-neutral request/response shapes. The internal format is
OpenAI-style (Hermes' choice — easiest to translate from):

- `Message(role: Literal["system","user","assistant","tool"], content: str | list[ContentBlock], name: str | None, tool_call_id: str | None, tool_calls: list[ToolCall] | None)`
- `ContentBlock` — text or image (image base64 + media_type)
- `ToolDefinition(name, description, parameters_json_schema)`
- `ToolCall(id, name, arguments_json)`
- `ChatRequest(model, messages, tools, tool_choice, temperature, max_tokens, stream, cache_breakpoints)`
- `ChatResponse(content, tool_calls, finish_reason, usage)`
- `StreamChunk(delta_text, tool_call_delta, finish_reason, usage)`
- `Usage(prompt_tokens, completion_tokens, cache_read_tokens, cache_write_tokens)`

### Adapters

Each adapter lives in its own module and translates between the internal
format and the provider's wire format.

- `anthropic_adapter.py` — uses the `anthropic` SDK. Maps to/from Messages API. Supports prompt caching via `cache_control` blocks and the cache breakpoint metadata in `ChatRequest`.
- `openai_adapter.py` — uses the `openai` SDK with Chat Completions API.
- `openrouter_adapter.py` — extends OpenAI adapter with OpenRouter base URL and required `HTTP-Referer` / `X-Title` headers from config.
- `compat_adapter.py` — generic OpenAI-compatible: takes a `base_url`, uses the OpenAI SDK pointed at it. Covers Ollama, vLLM, LM Studio, z.ai, Groq, Together, etc.

A factory `make_transport(model_config)` selects the right adapter based on
`provider`. Optional dependencies (`anthropic`, `openai`) are imported lazily
and raise a clear `TransportError` if missing, suggesting the install extra.

### Streaming

Both `chat` and `chat_stream` are required. Internally `chat` is implemented
as `chat_stream` consumed to completion. Streaming handles partial tool-call
arguments correctly (assemble JSON deltas).

### Interruption

`chat_stream` accepts an optional `cancel_event: threading.Event`. If the
event is set during iteration, the adapter aborts the underlying request
cleanly and raises `TransportError("interrupted", interrupted=True)`. This
mirrors Hermes' interruptibility.

### Prompt caching

When `cache_breakpoints: list[int]` is set in `ChatRequest`, the Anthropic
adapter inserts `cache_control: {type: "ephemeral"}` on the indicated message
indices. Other adapters ignore the field. The `Usage` object reports
`cache_read_tokens` and `cache_write_tokens` when available.

### Connectivity probe

`Transport.probe() -> ProbeResult` makes a tiny health-check request (1 token
output) to verify the connection. Used by `praxis doctor` and at orchestrator
startup.

### CLI additions

- `praxis doctor` — checks current profile's model config, runs `probe()` for the resolved model, and reports.
- `praxis ask "..."` — one-shot query: load profile, build a single-message ChatRequest, print the response. Useful smoke test.

---

## Deliverables

- `src/praxis/transport/` — base, models, factory, four adapters
- Updated `pyproject.toml` extras (already in chunk 01) used at import time with helpful error if missing
- `praxis doctor` and `praxis ask` CLI commands
- Unit tests per adapter using `respx` to mock HTTP (or the SDK's own mock support):
  - request shape correctness for each provider
  - response parsing (text-only, with tool calls, with cache stats)
  - streaming assembly (tool-call arguments across chunks)
  - interruption: cancel event aborts mid-stream
  - missing-key error handling (clear `TransportError` with env var name)
- Integration test: round-trip a fake conversation through each adapter using `respx` with realistic recorded fixtures
- `tests/integration/test_chunk_04.py` — `praxis ask "say 'pong'"` against a mocked Anthropic, expects "pong"
- `docs/reference/transport.md` — supported providers, config examples, env vars, OpenAI-compatible setup guide
- `docs/how-to/connect-openrouter.md`, `docs/how-to/connect-local-ollama.md`
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_anthropic_roundtrip(respx_mock, tmp_home_with_profile):
    respx_mock.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(200, json={
            "id": "msg_1", "type": "message",
            "content": [{"type": "text", "text": "pong"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 1}
        })
    )
    result = runner.invoke(app, ["ask", "say pong"])
    assert "pong" in result.stdout

def test_streaming_with_tool_calls(respx_mock, ...):
    # mock SSE stream that splits a tool call's arguments across chunks
    ...
    transport = make_transport(model_config)
    chunks = list(transport.chat_stream(req))
    assembled = assemble_tool_calls_from_stream(chunks)
    assert assembled[0].arguments_json == '{"x": 1, "y": 2}'

def test_interruption(respx_mock, ...):
    cancel = threading.Event()
    iterator = transport.chat_stream(req, cancel_event=cancel)
    next(iterator)
    cancel.set()
    with pytest.raises(TransportError) as ei:
        list(iterator)
    assert ei.value.details.get("interrupted") is True

def test_provider_factory_missing_dep(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(TransportError, match="install.*anthropic"):
        make_transport(ModelConfig(provider="anthropic", ...))
```

`pytest && ruff check && mypy src/praxis` all pass.

---

## Explicit non-goals

- No agent loop yet (chunk 8)
- No tools execution (chunk 5) — tool definitions and tool-call parsing are at the protocol level only
- No retries / circuit breakers — keep it simple for v1
- No cost tracking beyond reporting `Usage` per response

---

## Notes

- The `Transport` interface is intentionally narrow. Anything provider-specific
  belongs in the adapter, not the interface.
- Streaming returns chunks even when caller wants the full response —
  `chat()` is just `assemble(chat_stream(...))`. This avoids duplicate code
  paths.
- For OpenAI-compatible servers, document common pitfalls (model name conventions,
  missing tools support in some servers — adapter should report
  `supports_tools() = False` if the model name suggests it).
- Do not log or store API keys, even in error details.

---

## Definition of done

- All deliverables present
- All four adapters working against mocked responses
- Acceptance test passes
- `pytest`, `ruff`, `mypy` green
- `chunks/STATUS.md` updated
