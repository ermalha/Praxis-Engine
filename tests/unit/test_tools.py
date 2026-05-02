"""Tests for tool subsystem — registry, decorator, executor, approval."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock

import pytest

from praxis.config.models import ProfileConfig
from praxis.errors import ToolError
from praxis.tools import (
    ApprovalDecision,
    ToolContext,
    ToolRegistry,
    ToolResult,
    ToolSpec,
    default_registry,
    execute_tool_calls,
    tool,
)
from praxis.transport.models import ToolCall

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context() -> ToolContext:
    """Create a minimal ToolContext for testing."""
    return ToolContext(
        profile=ProfileConfig(name="test"),
        audit=MagicMock(),
    )


# Use a fresh registry per test to avoid cross-contamination
@pytest.fixture()
def registry() -> ToolRegistry:
    return ToolRegistry()


# ---------------------------------------------------------------------------
# Decorator & schema generation
# ---------------------------------------------------------------------------


class TestDecorator:
    def test_basic_registration(self) -> None:
        reg = ToolRegistry()

        def add(ctx: ToolContext, a: int, b: int) -> ToolResult:
            return ToolResult(content=str(a + b))

        spec = ToolSpec(
            name="add",
            description="add two ints",
            parameters_schema={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
            toolset="debug",
            dangerous=False,
            func=add,
        )
        reg.register(spec)
        assert reg.get("add") is not None

    def test_decorator_generates_schema(self) -> None:
        @tool(name="test_add", description="add", toolset="test")
        def test_add(ctx: ToolContext, a: int, b: int) -> ToolResult:
            return ToolResult(content=str(a + b))

        spec = default_registry.get("test_add")
        assert spec is not None
        assert spec.parameters_schema["properties"]["a"] == {"type": "integer"}  # type: ignore[index]
        assert spec.parameters_schema["properties"]["b"] == {"type": "integer"}  # type: ignore[index]
        assert "ctx" not in spec.parameters_schema.get("properties", {})  # type: ignore[union-attr]
        assert spec.parameters_schema.get("required") == ["a", "b"]

    def test_optional_params(self) -> None:
        @tool(name="test_opt", description="opt", toolset="test")
        def test_opt(ctx: ToolContext, name: str, count: int = 1) -> ToolResult:
            return ToolResult(content="ok")

        spec = default_registry.get("test_opt")
        assert spec is not None
        assert spec.parameters_schema.get("required") == ["name"]

    def test_literal_type(self) -> None:
        @tool(name="test_lit", description="lit", toolset="test")
        def test_lit(ctx: ToolContext, mode: Literal["fast", "slow"]) -> ToolResult:
            return ToolResult(content=mode)

        spec = default_registry.get("test_lit")
        assert spec is not None
        prop = spec.parameters_schema["properties"]["mode"]  # type: ignore[index]
        assert prop["enum"] == ["fast", "slow"]

    def test_list_type(self) -> None:
        @tool(name="test_list", description="list", toolset="test")
        def test_list(ctx: ToolContext, items: list[str]) -> ToolResult:
            return ToolResult(content=",".join(items))

        spec = default_registry.get("test_list")
        assert spec is not None
        prop = spec.parameters_schema["properties"]["items"]  # type: ignore[index]
        assert prop["type"] == "array"
        assert prop["items"] == {"type": "string"}

    def test_path_type(self) -> None:
        @tool(name="test_path", description="path", toolset="test")
        def test_path(ctx: ToolContext, filepath: Path) -> ToolResult:
            return ToolResult(content=str(filepath))

        spec = default_registry.get("test_path")
        assert spec is not None
        prop = spec.parameters_schema["properties"]["filepath"]  # type: ignore[index]
        assert prop["type"] == "string"
        assert prop["format"] == "path"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_list_by_toolset(self, registry: ToolRegistry) -> None:
        for name, ts in [("a", "core"), ("b", "debug"), ("c", "core")]:
            registry.register(
                ToolSpec(
                    name=name,
                    description=name,
                    parameters_schema={},
                    toolset=ts,
                    dangerous=False,
                    func=lambda ctx: ToolResult(content=""),
                )
            )
        assert len(registry.list_tools(toolset="core")) == 2
        assert len(registry.list_tools(toolset="debug")) == 1

    def test_to_definitions(self, registry: ToolRegistry) -> None:
        registry.register(
            ToolSpec(
                name="x",
                description="x tool",
                parameters_schema={"type": "object", "properties": {}},
                toolset="core",
                dangerous=False,
                func=lambda ctx: ToolResult(content=""),
            )
        )
        registry.register(
            ToolSpec(
                name="y",
                description="y tool",
                parameters_schema={"type": "object", "properties": {}},
                toolset="disabled",
                dangerous=False,
                func=lambda ctx: ToolResult(content=""),
            )
        )
        defs = registry.to_definitions({"core"})
        assert len(defs) == 1
        assert defs[0].name == "x"


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class TestExecutor:
    def test_basic_execution(self) -> None:
        reg = ToolRegistry()

        def add(ctx: ToolContext, a: int, b: int) -> ToolResult:
            return ToolResult(content=str(a + b), data={"sum": a + b})

        reg.register(
            ToolSpec(
                name="add",
                description="add",
                parameters_schema={},
                toolset="debug",
                dangerous=False,
                func=add,
            )
        )

        ctx = _make_context()
        results = execute_tool_calls(
            [ToolCall(id="c1", name="add", arguments_json='{"a": 2, "b": 3}')],
            ctx,
            registry=reg,
        )
        assert len(results) == 1
        assert results[0].content == "5"
        assert results[0].is_error is False

    def test_unknown_tool(self) -> None:
        reg = ToolRegistry()
        ctx = _make_context()
        results = execute_tool_calls(
            [ToolCall(id="c1", name="nonexistent", arguments_json="{}")],
            ctx,
            registry=reg,
        )
        assert results[0].is_error is True
        assert "Unknown tool" in results[0].content

    def test_invalid_json_args(self) -> None:
        reg = ToolRegistry()
        reg.register(
            ToolSpec(
                name="x",
                description="x",
                parameters_schema={},
                toolset="debug",
                dangerous=False,
                func=lambda ctx: ToolResult(content=""),
            )
        )
        ctx = _make_context()
        results = execute_tool_calls(
            [ToolCall(id="c1", name="x", arguments_json="{bad json}")],
            ctx,
            registry=reg,
        )
        assert results[0].is_error is True
        assert "Invalid JSON" in results[0].content

    def test_parallel_execution_is_parallel(self) -> None:
        reg = ToolRegistry()

        def slow(ctx: ToolContext, ms: int) -> ToolResult:
            time.sleep(ms / 1000.0)
            return ToolResult(content="done")

        reg.register(
            ToolSpec(
                name="slow",
                description="wait",
                parameters_schema={},
                toolset="debug",
                dangerous=False,
                func=slow,
            )
        )

        calls = [ToolCall(id=f"c{i}", name="slow", arguments_json='{"ms": 300}') for i in range(3)]
        ctx = _make_context()
        start = time.monotonic()
        results = execute_tool_calls(calls, ctx, registry=reg)
        elapsed = time.monotonic() - start

        assert len(results) == 3
        assert all(r.content == "done" for r in results)
        assert elapsed < 0.7  # 3 x 300ms parallel ≈ 300-400ms

    def test_interactive_forces_sequential(self) -> None:
        reg = ToolRegistry()
        order: list[str] = []

        def track(ctx: ToolContext, label: str) -> ToolResult:
            order.append(label)
            return ToolResult(content=label)

        reg.register(
            ToolSpec(
                name="track",
                description="track",
                parameters_schema={},
                toolset="debug",
                dangerous=False,
                interactive=True,
                func=track,
            )
        )

        calls = [
            ToolCall(id="c1", name="track", arguments_json='{"label": "first"}'),
            ToolCall(id="c2", name="track", arguments_json='{"label": "second"}'),
        ]
        ctx = _make_context()
        execute_tool_calls(calls, ctx, registry=reg)
        assert order == ["first", "second"]

    def test_dangerous_tool_blocked_without_approver(self) -> None:
        reg = ToolRegistry()
        reg.register(
            ToolSpec(
                name="risky",
                description="risky",
                parameters_schema={},
                toolset="debug",
                dangerous=True,
                func=lambda ctx: ToolResult(content="ok"),
            )
        )
        ctx = _make_context()
        with pytest.raises(ToolError, match="approval callback"):
            execute_tool_calls(
                [ToolCall(id="c1", name="risky", arguments_json="{}")],
                ctx,
                registry=reg,
                approval_callback=None,
            )

    def test_dangerous_tool_rejected(self) -> None:
        reg = ToolRegistry()
        reg.register(
            ToolSpec(
                name="risky",
                description="risky",
                parameters_schema={},
                toolset="debug",
                dangerous=True,
                func=lambda ctx: ToolResult(content="ok"),
            )
        )
        decisions: list[str] = []

        def approver(spec: ToolSpec, args: dict[str, object]) -> ApprovalDecision:
            decisions.append(spec.name)
            return ApprovalDecision.REJECT

        ctx = _make_context()
        results = execute_tool_calls(
            [ToolCall(id="c1", name="risky", arguments_json="{}")],
            ctx,
            registry=reg,
            approval_callback=approver,
        )
        assert decisions == ["risky"]
        assert "rejected" in results[0].content.lower()

    def test_dangerous_tool_approved(self) -> None:
        reg = ToolRegistry()
        reg.register(
            ToolSpec(
                name="risky",
                description="risky",
                parameters_schema={},
                toolset="debug",
                dangerous=True,
                func=lambda ctx: ToolResult(content="success"),
            )
        )

        def approver(spec: ToolSpec, args: dict[str, object]) -> ApprovalDecision:
            return ApprovalDecision.APPROVE

        ctx = _make_context()
        results = execute_tool_calls(
            [ToolCall(id="c1", name="risky", arguments_json="{}")],
            ctx,
            registry=reg,
            approval_callback=approver,
        )
        assert results[0].content == "success"

    def test_cancellation_between_calls(self) -> None:
        reg = ToolRegistry()
        reg.register(
            ToolSpec(
                name="noop",
                description="noop",
                parameters_schema={},
                toolset="debug",
                dangerous=False,
                interactive=True,  # Force sequential to test between calls
                func=lambda ctx: ToolResult(content="ok"),
            )
        )

        cancel = threading.Event()
        cancel.set()  # Pre-cancel

        ctx = _make_context()
        results = execute_tool_calls(
            [ToolCall(id="c1", name="noop", arguments_json="{}")],
            ctx,
            registry=reg,
            cancel_event=cancel,
        )
        assert results[0].is_error is True
        assert "cancelled" in results[0].content.lower()

    def test_tool_exception_returns_error_result(self) -> None:
        reg = ToolRegistry()

        def fail(ctx: ToolContext) -> ToolResult:
            msg = "something broke"
            raise ValueError(msg)

        reg.register(
            ToolSpec(
                name="fail",
                description="fail",
                parameters_schema={},
                toolset="debug",
                dangerous=False,
                func=fail,
            )
        )
        ctx = _make_context()
        results = execute_tool_calls(
            [ToolCall(id="c1", name="fail", arguments_json="{}")],
            ctx,
            registry=reg,
        )
        assert results[0].is_error is True
        assert "something broke" in results[0].content

    def test_audit_events_emitted(self) -> None:
        reg = ToolRegistry()
        reg.register(
            ToolSpec(
                name="echo",
                description="echo",
                parameters_schema={},
                toolset="debug",
                dangerous=False,
                func=lambda ctx, text="hi": ToolResult(content=text),
            )
        )
        ctx = _make_context()
        execute_tool_calls(
            [ToolCall(id="c1", name="echo", arguments_json='{"text": "hi"}')],
            ctx,
            registry=reg,
        )
        audit_calls = ctx.audit.call_args_list  # type: ignore[union-attr]
        event_types = [call[0][0] for call in audit_calls]
        assert "tool.invoked" in event_types
        assert "tool.completed" in event_types


# ---------------------------------------------------------------------------
# Builtins
# ---------------------------------------------------------------------------


class TestBuiltins:
    def test_echo_registered(self) -> None:

        spec = default_registry.get("echo")
        assert spec is not None
        assert spec.toolset == "debug"

    def test_sleep_is_interactive(self) -> None:

        spec = default_registry.get("sleep_seconds")
        assert spec is not None
        assert spec.interactive is True
