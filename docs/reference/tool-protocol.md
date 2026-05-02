# Tool Protocol Reference

## Defining a tool

```python
from praxis.tools import tool, ToolContext, ToolResult

@tool(
    name="search_glossary",
    description="Search the engagement glossary.",
    toolset="engagement",
    dangerous=False,
    interactive=False,
)
def search_glossary(ctx: ToolContext, query: str) -> ToolResult:
    # ... implementation ...
    return ToolResult(content="Found: ...", data={"matches": [...]})
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Unique tool name (used in LLM tool calls) |
| `description` | `str` | Shown to the LLM for tool selection |
| `toolset` | `str` | Grouping key for enable/disable |
| `dangerous` | `bool` | Requires human approval before execution |
| `interactive` | `bool` | Forces sequential execution |

## Schema generation

The `@tool` decorator inspects function type hints and generates a JSON
Schema for the LLM. Supported types:

| Python type | JSON Schema |
|---|---|
| `int` | `{"type": "integer"}` |
| `float` | `{"type": "number"}` |
| `bool` | `{"type": "boolean"}` |
| `str` | `{"type": "string"}` |
| `Path` | `{"type": "string", "format": "path"}` |
| `list[X]` | `{"type": "array", "items": ...}` |
| `dict[str, X]` | `{"type": "object", "additionalProperties": ...}` |
| `Literal["a", "b"]` | `{"type": "string", "enum": ["a", "b"]}` |
| `X \| None` | Schema of X (optional) |
| Pydantic model | Model's own JSON Schema |

The `ToolContext` parameter is always excluded from the schema.

## Executing tool calls

```python
from praxis.tools import execute_tool_calls
from praxis.transport.models import ToolCall

results = execute_tool_calls(
    calls=[ToolCall(id="c1", name="search_glossary", arguments_json='{"query": "stakeholder"}')],
    context=tool_context,
    approval_callback=cli_approval_callback,  # or None for non-dangerous
    cancel_event=cancel,  # optional threading.Event
)
```

### Execution behavior

- **Parallel**: Independent, non-interactive tools run concurrently (up to 4)
- **Sequential**: If any tool in the batch is `interactive=True`, all run in order
- **Cancellation**: Checked between calls; cancelled calls return error results
- **Errors**: Tool exceptions are caught and returned as error `ToolResultMessage`s

## Approval gate

```python
from praxis.tools import ApprovalDecision

def my_approver(spec, args):
    # Show spec.name, spec.description, args to user
    return ApprovalDecision.APPROVE  # or REJECT or MODIFY
```

## Audit events

| Event type | When |
|---|---|
| `tool.invoked` | Before execution starts |
| `tool.completed` | After successful execution |
| `tool.failed` | After an exception |
| `tool.rejected` | When approval gate rejects |

All events in a batch share a `correlation_id`.
