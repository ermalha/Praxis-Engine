"""Built-in tools for sanity checking the tool subsystem."""

from __future__ import annotations

import time

from praxis.tools.context import ToolContext
from praxis.tools.decorator import tool
from praxis.tools.models import ToolResult


@tool(name="echo", description="Return the input text unchanged.", toolset="debug")
def echo(_ctx: ToolContext, text: str) -> ToolResult:
    """Echo the input text back."""
    return ToolResult(content=text, data={"echoed": text})


@tool(
    name="sleep_seconds",
    description="Sleep for the given number of seconds.",
    toolset="debug",
    interactive=True,
)
def sleep_seconds(_ctx: ToolContext, seconds: float) -> ToolResult:
    """Sleep for a duration. Interactive — forces sequential execution."""
    time.sleep(seconds)
    return ToolResult(content=f"Slept for {seconds}s")
