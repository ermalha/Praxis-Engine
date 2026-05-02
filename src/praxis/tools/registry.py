"""Tool registry — catalog of available tools."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from praxis.tools.models import ToolResult
from praxis.transport.models import ToolDefinition


@dataclass(frozen=True)
class ToolSpec:
    """Specification for a registered tool."""

    name: str
    description: str
    parameters_schema: dict[str, object]
    toolset: str
    dangerous: bool
    func: Callable[..., ToolResult]
    interactive: bool = False


class ToolRegistry:
    """Mutable catalog of tool specifications."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        """Register a tool spec, overwriting any existing with the same name."""
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self, toolset: str | None = None) -> list[ToolSpec]:
        """List tools, optionally filtered by toolset."""
        specs = [*self._tools.values()]
        if toolset is not None:
            specs = [s for s in specs if s.toolset == toolset]
        return sorted(specs, key=lambda s: s.name)

    def to_definitions(self, enabled_toolsets: set[str]) -> list[ToolDefinition]:
        """Convert enabled tools to transport ``ToolDefinition`` objects."""
        return [
            ToolDefinition(
                name=spec.name,
                description=spec.description,
                parameters_json_schema=spec.parameters_schema,
            )
            for spec in self.list_tools()
            if spec.toolset in enabled_toolsets
        ]


default_registry = ToolRegistry()
