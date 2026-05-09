"""CLI error-handling decorator for clean user-facing errors."""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from typing import TypeVar

import typer
from rich.console import Console

from praxis.errors import PraxisError

F = TypeVar("F", bound=Callable[..., object])

_err_console = Console(stderr=True)


def handle_praxis_errors(fn: F) -> F:
    """Decorator that catches ``PraxisError`` and prints a clean message.

    Shows the full traceback only when ``PRAXIS_DEBUG=1``.
    """

    @functools.wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> object:
        try:
            return fn(*args, **kwargs)
        except PraxisError as exc:
            if os.environ.get("PRAXIS_DEBUG") == "1":
                _err_console.print_exception()
            else:
                label = type(exc).__name__
                _err_console.print(f"[red]{label}:[/red] {exc}")
            raise typer.Exit(1) from None

    return wrapper  # type: ignore[return-value]
