# Transport Layer Reference

The `praxis.transport` subsystem provides a provider-agnostic interface for
LLM communication. All agent code talks through a single `Transport` ABC;
concrete adapters translate to each provider's wire format.

---

## Supported Providers

| Provider | Adapter | SDK | Streaming | Tools | Caching |
|---|---|---|---|---|---|
| Anthropic | `AnthropicTransport` | `anthropic` | Yes | Yes | Yes |
| OpenAI | `OpenAITransport` | `openai` | Yes | Yes | No |
| OpenRouter | `OpenRouterTransport` | `openai` | Yes | Yes | No |
| OpenAI-compatible | `CompatTransport` | `openai` | Yes | No* | No |

*Local servers vary in tool support; the adapter defaults to `supports_tools() = False`.

---

## Configuration

Models are configured in profile YAML files under `model_aliases`:

```yaml
# ~/.praxis/profiles/default/profile.yaml
name: default
schema_version: 1
default_model_alias: default
model_aliases:
  default:
    schema_version: 1
    provider: anthropic
    model: claude-sonnet-4-20250514
    api_key_env: ANTHROPIC_API_KEY
    timeout_s: 120
  fast:
    schema_version: 1
    provider: openai
    model: gpt-4o-mini
    api_key_env: OPENAI_API_KEY
```

### Environment Variables

API keys are never stored in config files. The `api_key_env` field names the
environment variable that holds the key:

- `ANTHROPIC_API_KEY` — for Anthropic
- `OPENAI_API_KEY` — for OpenAI
- `OPENROUTER_API_KEY` — for OpenRouter
- Any name you choose — for OpenAI-compatible servers

---

## Factory

```python
from praxis.config import load_profile, resolve_model_config
from praxis.transport import make_transport

profile = load_profile("default")
model_config = resolve_model_config(profile)
transport = make_transport(model_config)
```

`make_transport()` lazily imports the required SDK. If the SDK isn't
installed, it raises `TransportError` with a clear install hint.

---

## Streaming

Both `chat()` and `chat_stream()` are available. Internally, `chat()` calls
`chat_stream()` and assembles the full response. Streaming correctly handles
partial tool-call arguments across chunks.

```python
for chunk in transport.chat_stream(request):
    if chunk.delta_text:
        print(chunk.delta_text, end="")
```

---

## Interruption

Pass a `threading.Event` to abort mid-stream:

```python
import threading

cancel = threading.Event()
iterator = transport.chat_stream(request, cancel_event=cancel)
# ... in another thread: cancel.set()
```

When set, the adapter raises `TransportError("Request interrupted", interrupted=True)`.

---

## Prompt Caching (Anthropic)

Set `cache_breakpoints` in `ChatRequest` to mark which message indices
should receive `cache_control: {type: "ephemeral"}`:

```python
request = ChatRequest(
    model="claude-sonnet-4-20250514",
    messages=[system_msg, context_msg, user_msg],
    cache_breakpoints=[1],  # cache the context message
)
```

Usage stats include `cache_read_tokens` and `cache_write_tokens`.

---

## CLI Commands

- `praxis ask "question"` — one-shot query using the default profile's model
- `praxis doctor` — check config and probe the resolved transport

---

## Connectivity Probe

```python
result = transport.probe()
if result.ok:
    print(f"Connected in {result.latency_ms:.0f}ms")
else:
    print(f"Failed: {result.error}")
```
