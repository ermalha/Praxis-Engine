"""@tool decorator — registers functions into the default registry."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

from praxis.tools.context import ToolContext
from praxis.tools.models import ToolResult
from praxis.tools.registry import ToolSpec, default_registry


def tool(
    name: str,
    description: str,
    toolset: str,
    *,
    dangerous: bool = False,
    interactive: bool = False,
) -> Callable[[Callable[..., ToolResult]], Callable[..., ToolResult]]:
    """Decorator that registers a function as a tool.

    Inspects the function's type hints to generate a JSON Schema for
    ``parameters_schema``. The ``ToolContext`` parameter is excluded from
    the schema and injected at call time.
    """

    def decorator(func: Callable[..., ToolResult]) -> Callable[..., ToolResult]:
        schema = _build_schema(func)
        spec = ToolSpec(
            name=name,
            description=description,
            parameters_schema=schema,
            toolset=toolset,
            dangerous=dangerous,
            interactive=interactive,
            func=func,
        )
        default_registry.register(spec)
        return func

    return decorator


def _build_schema(func: Callable[..., Any]) -> dict[str, object]:
    """Build a JSON Schema from a function's type hints."""
    sig = inspect.signature(func)
    hints = _get_type_hints_safe(func)

    properties: dict[str, object] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        # Skip ToolContext — injected at call time
        hint = hints.get(param_name)
        if hint is ToolContext or param_name == "ctx":
            continue
        # Skip **kwargs and *args
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue

        prop = _type_to_schema(hint)
        properties[param_name] = prop

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    schema: dict[str, object] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def _get_type_hints_safe(func: Callable[..., Any]) -> dict[str, Any]:
    """Get type hints, handling forward references gracefully."""
    try:
        return inspect.get_annotations(func, eval_str=True)
    except Exception:
        return inspect.get_annotations(func)


def _type_to_schema(hint: Any) -> dict[str, object]:
    """Convert a Python type hint to a JSON Schema fragment."""
    if hint is None or hint is type(None):
        return {"type": "null"}

    # Handle Optional[X] (Union[X, None])
    origin = get_origin(hint)
    args = get_args(hint)

    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            # Optional[X]
            return _type_to_schema(non_none[0])
        return {"anyOf": [_type_to_schema(a) for a in args]}

    # Literal
    if origin is Literal:
        values = list(args)
        if all(isinstance(v, str) for v in values):
            return {"type": "string", "enum": values}
        return {"enum": values}

    # list[X]
    if origin is list:
        if args:
            return {"type": "array", "items": _type_to_schema(args[0])}
        return {"type": "array"}

    # dict[str, X]
    if origin is dict:
        if len(args) >= 2:
            return {"type": "object", "additionalProperties": _type_to_schema(args[1])}
        return {"type": "object"}

    # Pydantic models — use their built-in JSON Schema
    if isinstance(hint, type):
        from pydantic import BaseModel

        if issubclass(hint, BaseModel):
            return hint.model_json_schema()

    # Primitives
    if hint is int:
        return {"type": "integer"}
    if hint is float:
        return {"type": "number"}
    if hint is bool:
        return {"type": "boolean"}
    if hint is str:
        return {"type": "string"}
    if hint is Path:
        return {"type": "string", "format": "path"}

    # Fallback
    return {"type": "string"}
