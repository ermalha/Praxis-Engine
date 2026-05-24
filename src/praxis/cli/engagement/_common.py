"""Shared helpers for the engagement CLI subcommands.

Extracted from the monolithic ``engagement_cmd.py`` as part of the D-064
split. All sibling modules under ``praxis.cli.engagement`` import their
``_resolve_engagement`` / ``_audit_ctx`` / ``console`` / ``err_console``
from here so option parsing + audit framing stay consistent across the
nine entity-specific submodules.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import typer
from rich.console import Console

from praxis.audit.context import set_audit_context
from praxis.config.engagement import find_engagement
from praxis.config.loader import load_engagement_config

console = Console()
err_console = Console(stderr=True)


def _resolve_engagement(engagement: str | None) -> Path:
    """Resolve the engagement path from the option or CWD."""
    if engagement is not None:
        p = Path(engagement)
        if not (p / ".praxis").is_dir():
            err_console.print(f"[red]Not an engagement: {p}[/red]")
            raise typer.Exit(1)
        return p

    found = find_engagement(Path.cwd())
    if found is None:
        err_console.print("[red]No engagement found. Use --engagement or cd into one.[/red]")
        raise typer.Exit(1)
    return found


def _audit_ctx(eng: Path) -> contextlib.AbstractContextManager[object]:
    """Return an audit context manager scoped to *eng*."""
    config = load_engagement_config(eng)
    return set_audit_context(engagement=config.name, engagement_path=eng)
