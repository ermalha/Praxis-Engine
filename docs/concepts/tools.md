# Tools

Tools are how the Praxis agent acts on the world. Each tool is a Python
function decorated with `@tool(...)` that the LLM can invoke during
a conversation turn.

## How tools work

1. The **registry** holds all available tools as `ToolSpec` objects
2. The **decorator** (`@tool`) auto-generates a JSON Schema from type hints
3. The **executor** runs tool calls — in parallel when safe, sequentially
   when any tool is `interactive=True`
4. The **approval gate** blocks dangerous tools until a human approves

## ToolContext

Every tool receives a `ToolContext` as its first argument, providing:

- `profile` — the active profile config
- `engagement` — the engagement config (if any)
- `engagement_path` — path to the engagement directory
- `audit` — bound audit emit function
- `db` — SQLite connection (if available)
- `config` — global config

## Tool lifecycle

```
LLM returns tool_calls
    → executor parses arguments
    → checks for dangerous tools → approval gate
    → runs tools (parallel or sequential)
    → emits audit events (tool.invoked, tool.completed/tool.failed)
    → returns ToolResultMessages to the LLM
```

## Key design decisions

- Tools **never call the LLM** — that's the agent's responsibility
- `dangerous=True` requires an approval callback; no callback = `ToolError`
- `interactive=True` forces sequential execution (e.g., for tools that
  need user input or have ordering dependencies)
- Tool failures return error results to the LLM rather than crashing,
  allowing the agent to recover
- All tool executions emit audit events with a shared `correlation_id`
  per batch
