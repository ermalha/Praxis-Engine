# Agent Loop

The Praxis agent is a turn-based conversational agent that uses tool calling to
interact with the engagement model and external resources.

## Architecture

```
User input
    ↓
[Persist user message]
    ↓
[Build system prompt + history]
    ↓
┌─→ [Call LLM via transport] ──→ text response → persist & return
│           ↓
│   tool_calls in response?
│           ↓ yes
│   [Execute tools via executor]
│           ↓
│   [Persist assistant + tool messages]
│           ↓
└───────────┘ (loop, up to max_iterations)
```

## Key components

### Agent class (`src/praxis/core/agent.py`)

The `Agent` class manages a session and executes turns:

- `start_session()` — creates a DB-backed session
- `turn(user_input)` — full turn, returns `AgentResponse`
- `stream_turn(user_input)` — yields `StreamEvent` objects
- `end_session()` — closes the session with optional summary

### Prompt builder (`src/praxis/core/prompt.py`)

Composes the system prompt from:
1. Personality (Praxis baseline persona)
2. Engagement summary (name, methodology)
3. Skill index (level 0: name + description per active skill)
4. Tool use guidance
5. Engagement model quick refs (glossary count, stakeholders, etc.)

The prompt is **cache-stable** — it doesn't change within a session unless
something material changes.

### Session management (`src/praxis/core/session.py`)

Sessions and messages persist to SQLite. Messages are FTS5-indexed for
search via the `session_search` tool.

## Turn limits

- **max_tool_iterations**: 25 by default. If the agent calls tools in a loop
  without producing a final text response, the turn is truncated after this
  many iterations. The response is marked `truncated=True`.

## Built-in tools

| Tool | Toolset | Dangerous | Description |
|------|---------|-----------|-------------|
| `current_time` | agent | No | Current UTC datetime |
| `session_search` | agent | No | FTS5 search over conversation history |
| `read_file` | agent | No | Read from engagement artifacts |
| `write_file` | agent | Yes | Write to engagement artifacts |
| `web_fetch` | agent | No | Basic HTTP GET |

Plus all engagement tools from Chunk 07 and skill tools from Chunk 06.
