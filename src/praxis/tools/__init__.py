"""Praxis tool subsystem — registry, execution, and approval."""

# Auto-register built-in tools when the package is imported
import praxis.tools.builtin as _builtin  # noqa: F401
from praxis.tools.context import ToolContext
from praxis.tools.decorator import tool
from praxis.tools.executor import execute_tool_calls
from praxis.tools.models import ApprovalDecision, ToolResult, ToolResultMessage
from praxis.tools.registry import ToolRegistry, ToolSpec, default_registry

__all__ = [
    "ApprovalDecision",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "ToolResultMessage",
    "ToolSpec",
    "default_registry",
    "execute_tool_calls",
    "tool",
]
