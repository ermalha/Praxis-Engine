"""Tool executor — runs tool calls with parallel execution, approval, and audit."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import structlog

from praxis.errors import ToolError
from praxis.tools.context import ToolContext
from praxis.tools.models import ApprovalDecision, ToolResultMessage
from praxis.tools.registry import ToolRegistry, ToolSpec, default_registry
from praxis.transport.models import ToolCall

logger = structlog.get_logger()

_MAX_WORKERS = 4


def execute_tool_calls(
    calls: list[ToolCall],
    context: ToolContext,
    *,
    approval_callback: Callable[[ToolSpec, dict[str, object]], ApprovalDecision] | None = None,
    cancel_event: threading.Event | None = None,
    registry: ToolRegistry | None = None,
) -> list[ToolResultMessage]:
    """Execute a batch of tool calls.

    Independent calls run in parallel (up to ``_MAX_WORKERS``).
    If any call is ``interactive=True``, all calls run sequentially.
    """
    reg = registry or default_registry
    correlation_id = str(uuid.uuid4())

    # Check if any tool is interactive → force sequential
    force_sequential = False
    for call in calls:
        spec = reg.get(call.name)
        if spec and spec.interactive:
            force_sequential = True
            break

    if force_sequential or len(calls) == 1:
        return [
            _execute_single(call, context, reg, approval_callback, cancel_event, correlation_id)
            for call in calls
        ]

    results: list[ToolResultMessage | None] = [None] * len(calls)
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(calls))) as pool:
        futures = {
            pool.submit(
                _execute_single,
                call,
                context,
                reg,
                approval_callback,
                cancel_event,
                correlation_id,
            ): i
            for i, call in enumerate(calls)
        }
        for future in futures:
            idx = futures[future]
            results[idx] = future.result()

    return [r for r in results if r is not None]


def _execute_single(
    call: ToolCall,
    context: ToolContext,
    registry: ToolRegistry,
    approval_callback: Callable[[ToolSpec, dict[str, object]], ApprovalDecision] | None,
    cancel_event: threading.Event | None,
    correlation_id: str,
) -> ToolResultMessage:
    """Execute a single tool call with approval checks and audit."""
    spec = registry.get(call.name)
    if spec is None:
        return ToolResultMessage(
            tool_call_id=call.id,
            content=f"Unknown tool: {call.name}",
            is_error=True,
        )

    # Parse arguments
    try:
        args: dict[str, object] = json.loads(call.arguments_json) if call.arguments_json else {}
    except json.JSONDecodeError as exc:
        return ToolResultMessage(
            tool_call_id=call.id,
            content=f"Invalid JSON arguments: {exc}",
            is_error=True,
        )

    # Check cancel
    if cancel_event and cancel_event.is_set():
        return ToolResultMessage(
            tool_call_id=call.id,
            content="Execution cancelled",
            is_error=True,
        )

    # Dangerous tool approval
    if spec.dangerous:
        if approval_callback is None:
            raise ToolError(
                "Dangerous tool invoked without an approval callback",
                tool=spec.name,
            )
        decision = approval_callback(spec, args)
        if decision == ApprovalDecision.REJECT:
            context.audit(
                "tool.rejected",
                component="tools",
                subject_id=spec.name,
                correlation_id=correlation_id,
                tool=spec.name,
                args=args,
            )
            return ToolResultMessage(
                tool_call_id=call.id,
                content=f"Tool '{spec.name}' was rejected by the approval gate.",
                is_error=False,
            )

    # Emit invocation audit
    context.audit(
        "tool.invoked",
        component="tools",
        subject_id=spec.name,
        correlation_id=correlation_id,
        tool=spec.name,
        args=args,
    )

    # Execute
    try:
        result = spec.func(context, **args)
        context.audit(
            "tool.completed",
            component="tools",
            subject_id=spec.name,
            correlation_id=correlation_id,
            tool=spec.name,
        )
        return ToolResultMessage(
            tool_call_id=call.id,
            content=result.content,
        )
    except Exception as exc:
        logger.error("tool.failed", tool=spec.name, error=str(exc))
        context.audit(
            "tool.failed",
            component="tools",
            subject_id=spec.name,
            correlation_id=correlation_id,
            tool=spec.name,
            error=str(exc),
        )
        return ToolResultMessage(
            tool_call_id=call.id,
            content=f"Tool '{spec.name}' failed: {exc}",
            is_error=True,
        )
