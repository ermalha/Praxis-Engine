# Chunk 08 — Conversation Loop (the basic agent)

**Phase:** Agent Core | **Estimated effort:** 5–6 hours | **Dependencies:** 01–07

---

## Context

We now have transport, tools, skills, and engagement memory. This chunk wires
them together into a working chat agent — turn-based, Hermes-style. After
this chunk, `praxis chat` opens a REPL where you can talk to the agent, it
calls tools, it remembers conversation history, it persists sessions, and it
can read/write the engagement model.

This is the **mini-Hermes milestone**. Praxis becomes useful here for the first time.
Chunks 9–12 then add the proactive agent-led behavior on top.

---

## Scope

### The Agent class (`src/praxis/core/agent.py`)

A single class that handles a turn-based conversation:

```python
class Agent:
    def __init__(
        self,
        profile: ProfileConfig,
        engagement: EngagementConfig | None,
        engagement_path: Path | None,
        transport: Transport,
        tool_registry: ToolRegistry,
        skill_registry: SkillRegistry,
        approval_callback: Callable | None = None,
    ): ...

    def start_session(self, parent_id: str | None = None) -> str: ...    # returns session id
    def turn(self, user_input: str, *, cancel_event: Event | None = None) -> AgentResponse: ...
    def stream_turn(self, user_input: str, *, cancel_event: Event | None = None) -> Iterator[StreamEvent]: ...
    def end_session(self, summary: str | None = None) -> None: ...
```

`turn()` is `stream_turn()` consumed to completion.

### Turn algorithm

```
1. Persist user message to messages table (role=user)
2. Build system prompt (see prompt builder below)
3. Build provider tool definitions from registry, filtered by enabled toolsets
4. Loop:
   a. Call transport.chat_stream(...)
   b. Stream events out (text deltas, tool-call deltas, status)
   c. When stream completes:
      - If finish_reason == "tool_use" / "tool_calls":
          execute via tool executor (may prompt for approval)
          persist assistant message with tool_calls + tool result messages
          continue loop
      - Else:
          persist assistant message
          break
5. Update session metadata
6. Return AgentResponse(content, tool_call_count, usage_total, session_id)
```

Limits:
- Max iterations per turn: 25 (configurable via `max_tool_iterations` in profile)
- Max tool calls in parallel: per chunk-5 executor limit
- Honor `cancel_event` between iterations and pass to transport

### Prompt builder (`src/praxis/core/prompt.py`)

Composes the system prompt from layered sources (Hermes pattern):

```
[Personality]   <- praxis baseline persona (minimal in v1)
[Engagement Summary]  <- name, methodology, top-level stats
[Skill Index Level 0]  <- name + description per active skill
[Tool Use Guidance]    <- generic rules + specific overrides
[Engagement Model Quick Refs]  <- glossary count, top stakeholders, open questions count
[User Preferences]     <- from profile config
```

**Cache-stable**: the system prompt MUST NOT change within a session unless
something material changes (skill added, engagement renamed). When using the
Anthropic transport, mark the system prompt as a cache breakpoint.

The prompt builder lives in `core/prompt.py` and is unit-testable in isolation
(returns a string, given a stable input).

### Session & message persistence

- Each `praxis chat` invocation starts a session, all turns persist messages.
- On `Ctrl-C` or `/exit`: end session, optionally generate a one-line summary
  via a final tiny LLM call (skip if config disables this for cost).
- `praxis sessions list / show / resume <id>` for navigation.

### Built-in tools available to the agent

From earlier chunks: skill_list, skill_view, skill_manage, all engagement
tools. Plus this chunk adds:

- `session_search(query)` — FTS5 lookup over historical messages
- `read_file(path)` — read a file from the engagement workspace (`.praxis/artifacts/`)
- `write_file(path, content)` — `dangerous=True`; write to engagement workspace
- `web_fetch(url)` — fetch a URL (basic; no JS rendering); `dangerous=False` but capped at one per turn
- `current_time()` — current UTC datetime

### CLI: `praxis chat`

Opens a REPL using `prompt_toolkit` or rich-based loop:

- Prints assistant streamed output as it arrives
- Shows tool-call invocations (collapsed by default; expandable with `/last`)
- Approval gate prompts inline for dangerous tools (using chunk-5 callback)
- Slash commands:
  - `/exit` — end session
  - `/new` — start a new session
  - `/sessions` — list recent
  - `/resume <id>` — resume a session
  - `/skills` — list active skills
  - `/tools` — list available tools
  - `/audit` — show last 10 events
  - `/help`

### Audit events

- `session.started`, `session.ended`
- `turn.started`, `turn.completed`
- `agent.tool_called` (correlates with chunk-5 `tool.invoked`)
- `agent.message_sent` (assistant message, hash of content for de-dup not full text)

---

## Deliverables

- `src/praxis/core/agent.py`
- `src/praxis/core/prompt.py`
- `src/praxis/core/session.py` (session lifecycle helpers)
- 5 new built-in tools (session_search, read_file, write_file, web_fetch, current_time)
- CLI: `praxis chat`, `praxis sessions list/show/resume`
- Tests:
  - Prompt builder produces deterministic output for stable input
  - Agent.turn round-trip with mocked transport: text-only response, single tool call, multi-tool-call, parallel tool calls, max-iterations cap, cancellation
  - Session persistence: messages saved, FTS searchable
  - `session_search` tool returns hits
  - `write_file` requires approval and writes to engagement workspace only (rejects path traversal)
- `tests/integration/test_chunk_08.py` — full chat session: ask the agent to "add 'invoice' to the glossary as 'a request for payment'", confirm engagement model is updated and audit events are emitted
- `docs/concepts/agent-loop.md`
- `docs/how-to/first-chat.md` (the user's first 5 minutes with Praxis)
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_agent_can_update_engagement_via_chat(tmp_engagement, mock_anthropic):
    # Mock the LLM to: first turn returns a tool_call to glossary_add_term;
    # second turn returns a friendly confirmation.
    mock_anthropic.queue_response(tool_calls=[ToolCall(
        id="c1", name="glossary_add_term",
        arguments_json='{"term":"invoice","definition":"A request for payment"}'
    )])
    mock_anthropic.queue_response(text="Added 'invoice' to the glossary.")

    agent = make_agent(tmp_engagement)
    sess = agent.start_session()
    resp = agent.turn("Please add 'invoice' to the glossary as 'A request for payment'.",
                      approval_callback=lambda *a, **k: ApprovalDecision.APPROVE)
    assert "added" in resp.content.lower() or "invoice" in resp.content.lower()

    glossary = GlossaryRepo(tmp_engagement).load()
    assert any(t.term == "invoice" for t in glossary.terms)

    # Session persisted
    sessions = SessionsRepo(...).list()
    assert sess in {s.id for s in sessions}

def test_max_iterations_cap(tmp_engagement, mock_anthropic):
    # Mock returns tool calls forever
    for _ in range(100):
        mock_anthropic.queue_response(tool_calls=[...])
    with pytest.raises(...) or assert turn returns with truncation marker
```

---

## Explicit non-goals

- No proactive wake cycle (chunk 12)
- No sufficiency gate (chunk 9)
- No work-queue (chunk 11)
- No TUI (chunk 13)
- No browser (chunk 14)
- The agent here is reactive, like Hermes. The Praxis distinctives come next.

---

## Notes

- Keep the prompt minimal. The temptation is to write a 5000-word system
  prompt. Resist. The skills + engagement model + tools should carry most of
  the agent's behavior, not the prompt.
- The prompt builder's deterministic output is critical for cache hits. Keep
  ordering of sections stable; never include time-varying content (current
  time, user input) in the cached portion.
- For mocked-LLM tests: build a simple `MockTransport` in `tests/conftest.py`
  with a `queue_response(...)` method. Don't go through respx for these — too
  fragile for streaming tool calls.
- `write_file` must validate the path is within `<engagement>/.praxis/artifacts/`.
  Reject anything else with `ToolError`.

---

## Definition of done

- All deliverables present
- `praxis chat` is genuinely usable end-to-end against a real model
- Acceptance test passes
- `pytest`, `ruff`, `mypy` green
- `chunks/STATUS.md` updated — **mini-Hermes milestone reached**
