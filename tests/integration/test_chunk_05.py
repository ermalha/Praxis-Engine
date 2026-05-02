"""Chunk 05 acceptance test — tool registry and execution end-to-end."""

from __future__ import annotations

from unittest.mock import MagicMock

from praxis.config.models import ProfileConfig
from praxis.tools import (
    ApprovalDecision,
    ToolContext,
    ToolResult,
    ToolSpec,
    default_registry,
    execute_tool_calls,
    tool,
)
from praxis.transport.models import ToolCall


def _make_context() -> ToolContext:
    return ToolContext(profile=ProfileConfig(name="test"), audit=MagicMock())


def test_decorator_registers_and_runs() -> None:
    """Full flow: register via decorator, inspect schema, execute, verify."""

    @tool(name="integ_add", description="add two ints", toolset="debug")
    def integ_add(ctx: ToolContext, a: int, b: int) -> ToolResult:
        return ToolResult(content=str(a + b), data={"sum": a + b})

    spec = default_registry.get("integ_add")
    assert spec is not None
    assert spec.parameters_schema["properties"]["a"]["type"] == "integer"  # type: ignore[index]
    assert "ctx" not in spec.parameters_schema["properties"]  # type: ignore[index]

    ctx = _make_context()
    results = execute_tool_calls(
        [ToolCall(id="c1", name="integ_add", arguments_json='{"a": 2, "b": 3}')],
        ctx,
    )
    assert results[0].content == "5"


def test_dangerous_tool_approval_flow() -> None:
    """Dangerous tools go through approval; REJECT prevents execution."""

    @tool(name="integ_risky", description="risky op", toolset="debug", dangerous=True)
    def integ_risky(ctx: ToolContext) -> ToolResult:
        return ToolResult(content="executed")

    decisions: list[str] = []

    def approver(spec: ToolSpec, args: dict[str, object]) -> ApprovalDecision:
        decisions.append(spec.name)
        return ApprovalDecision.REJECT

    ctx = _make_context()
    results = execute_tool_calls(
        [ToolCall(id="c1", name="integ_risky", arguments_json="{}")],
        ctx,
        approval_callback=approver,
    )
    assert decisions == ["integ_risky"]
    assert "rejected" in results[0].content.lower()


def test_tool_definitions_for_transport() -> None:
    """Registry can produce ToolDefinitions for the transport layer."""

    defs = default_registry.to_definitions({"debug"})
    names = {d.name for d in defs}
    assert "echo" in names
    assert "sleep_seconds" in names
