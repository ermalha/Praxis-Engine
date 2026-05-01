# Chunk 05 — Tool Registry & Execution

**Phase:** Agent Core | **Estimated effort:** 4–5 hours | **Dependencies:** 01–04

---

## Context

Tools are how the agent acts. The registry is the catalog the LLM sees; the
executor runs the tools the model selected. Both must be safe (dangerous-action
gate), parallel-friendly (independent tool calls run concurrently), and audit-emitting.

---

## Scope

### Registry (`src/praxis/tools/registry.py`)

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters_schema: dict          # JSON Schema
    toolset: str                     # for grouping & enable/disable
    dangerous: bool                  # requires approval before execution
    func: Callable[..., ToolResult]
    interactive: bool = False        # cannot run in parallel with others

class ToolRegistry:
    def register(self, spec: ToolSpec) -> None: ...
    def get(self, name: str) -> ToolSpec | None: ...
    def list(self, toolset: str | None = None) -> list[ToolSpec]: ...
    def to_definitions(self, enabled_toolsets: set[str]) -> list[ToolDefinition]: ...
```

A module-level `default_registry: ToolRegistry` exists. The `@tool(...)` decorator
self-registers into it (Hermes pattern).

### Decorator (`src/praxis/tools/decorator.py`)

```python
def tool(
    name: str,
    description: str,
    toolset: str,
    *,
    dangerous: bool = False,
    interactive: bool = False,
) -> Callable[[Callable], Callable]: ...
```

Inspects the wrapped function's signature (Python type hints) and constructs
a JSON Schema for `parameters_schema` automatically. Required params: those
without defaults. Optional: those with defaults. `ToolContext` parameter is
NOT exposed in the schema — it's injected at call time.

### Execution (`src/praxis/tools/executor.py`)

```python
def execute_tool_calls(
    calls: list[ToolCall],
    context: ToolContext,
    *,
    approval_callback: Callable[[ToolSpec, dict], ApprovalDecision] | None,
    cancel_event: threading.Event | None = None,
) -> list[ToolResultMessage]: ...
```

Behavior:
- Group calls into a sequential queue if any is `interactive=True`; otherwise
  run independent calls in parallel via `ThreadPoolExecutor` (max 4 workers).
- Before executing a `dangerous=True` tool, invoke `approval_callback`. If it
  returns `ApprovalDecision.REJECT`, return a synthetic tool result indicating
  rejection. If `approval_callback` is None and tool is dangerous, raise
  `ToolError("dangerous tool without approver")`.
- Honor `cancel_event` between calls and (where the tool supports it) within them.
- Emit audit events `tool.invoked` and `tool.completed` (or `tool.failed`).
- Always return a `ToolResultMessage` per call (even on error) so the LLM sees
  failures and can recover.

### ToolContext (`src/praxis/tools/context.py`)

```python
@dataclass
class ToolContext:
    profile: ProfileConfig
    engagement: EngagementConfig | None
    engagement_path: Path | None
    audit: Callable[..., AuditEvent]   # bound emit() with context
    db: sqlite3.Connection | None
    config: GlobalConfig
```

Tools receive this as their first arg. The agent constructs it once per turn.

### Approval gate

`src/praxis/tools/approval.py` defines:

```python
class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"

def cli_approval_callback(spec: ToolSpec, args: dict) -> ApprovalDecision: ...
```

`cli_approval_callback` prompts the user via `rich` with the tool name,
arguments, and a [a]pprove/[r]eject/[m]odify choice. (Used in CLI mode; TUI
provides its own.)

A config flag `auto_approve: bool` (default False) bypasses the gate — only
honored when set in the profile config and never via CLI flag, to make
unsafe automation deliberate.

### Two starter tools (sanity checks)

To exercise the registry end-to-end:

- `praxis.tools.builtin.echo` — toolset="debug", dangerous=False, returns its arg
- `praxis.tools.builtin.sleep_seconds` — toolset="debug", interactive=True, demonstrates ordering

### CLI additions

- `praxis tool list [--toolset T]`
- `praxis tool describe <name>` — print the JSON Schema
- `praxis tool call <name> '<args-json>'` — invoke a tool directly (developer aid; only available with `--profile <p>` having `developer_mode: true`)

---

## Deliverables

- `src/praxis/tools/` — registry, decorator, executor, context, approval, builtin
- Tests covering:
  - Decorator generates correct JSON Schema for various signatures (incl. Optional, Literal, list, Pydantic models)
  - Registry self-registration
  - Parallel execution: 3 independent tools complete within wallclock < sum of their sleeps
  - Interactive flag forces sequential
  - Dangerous tool blocked without approver
  - Dangerous tool runs after APPROVE; doesn't run after REJECT
  - Cancellation between calls
  - Audit events emitted with correct correlation_id grouping calls in one turn
- `tests/integration/test_chunk_05.py` — full flow: register tool, simulate model returning a tool call, execute, verify result
- `docs/concepts/tools.md` and `docs/reference/tool-protocol.md`
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_decorator_registers_and_runs(tmp_engagement):
    @tool(name="add", description="add two ints", toolset="debug")
    def add(ctx: ToolContext, a: int, b: int) -> ToolResult:
        return ToolResult(content=str(a + b), data={"sum": a + b})

    spec = default_registry.get("add")
    assert spec is not None
    assert spec.parameters_schema["properties"]["a"]["type"] == "integer"
    assert "ctx" not in spec.parameters_schema["properties"]

    ctx = make_test_context(engagement=tmp_engagement)
    results = execute_tool_calls(
        [ToolCall(id="c1", name="add", arguments_json='{"a":2,"b":3}')],
        context=ctx,
        approval_callback=None,
    )
    assert results[0].content == "5"

def test_parallel_execution_is_parallel(tmp_engagement):
    @tool(name="slow", description="wait", toolset="debug")
    def slow(ctx: ToolContext, ms: int) -> ToolResult:
        time.sleep(ms / 1000.0)
        return ToolResult(content="done")

    calls = [ToolCall(id=f"c{i}", name="slow",
                      arguments_json='{"ms":300}') for i in range(3)]
    start = time.monotonic()
    execute_tool_calls(calls, context=make_test_context(...), approval_callback=None)
    elapsed = time.monotonic() - start
    assert elapsed < 0.7   # 3 × 300ms in parallel ≈ 300-400ms

def test_dangerous_tool_requires_approval():
    @tool(name="risky", description="risky", toolset="debug", dangerous=True)
    def risky(ctx: ToolContext) -> ToolResult: return ToolResult(content="ok")

    decisions = []
    def approver(spec, args):
        decisions.append(spec.name)
        return ApprovalDecision.REJECT
    results = execute_tool_calls(
        [ToolCall(id="c1", name="risky", arguments_json="{}")],
        context=..., approval_callback=approver,
    )
    assert decisions == ["risky"]
    assert "rejected" in results[0].content.lower()
```

---

## Explicit non-goals

- No actual BA tools yet (those are mostly chunk 14)
- No skills (chunk 6)
- No browser harness integration (chunk 14)

---

## Notes

- JSON Schema generation for type hints: handle `int`, `float`, `bool`, `str`,
  `list[X]`, `dict[str, X]`, `Literal[...]`, `Optional[X]`, Pydantic models
  (which carry their own schema), and `Path` (treated as string with format).
- Tools that need to call the LLM transport must NOT — that's a layer violation.
  If a tool needs LLM analysis, it returns data and the agent decides what to do.
- The approval CLI prompt should clearly show *what* would happen, not just the
  tool name. Print arguments via `rich.json()`.
- Audit `correlation_id`: the executor groups all tool calls in one batch
  under a shared correlation id, so the audit trail can reconstruct the turn.

---

## Definition of done

- All deliverables present
- Acceptance test passes
- `pytest`, `ruff`, `mypy` green
- Coverage ≥ 80% on tools subsystem
- `chunks/STATUS.md` updated
