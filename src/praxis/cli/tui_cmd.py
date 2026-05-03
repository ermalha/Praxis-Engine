"""CLI command: ``praxis tui`` — launch the TUI."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from praxis.config.engagement import find_engagement

err_console = Console(stderr=True)


def _resolve_eng(engagement: str | None) -> Path:
    eng = Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    if eng is None:
        err_console.print("[red]No engagement found.[/red]")
        raise typer.Exit(1)
    return eng


def tui(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    _screen: str = typer.Option("queue", "--screen", "-s", help="Initial screen."),
) -> None:
    """Launch the Praxis TUI."""
    eng = _resolve_eng(engagement)

    try:
        from praxis.tui.app import PraxisApp
    except ImportError:
        err_console.print("[red]textual not installed. Install: pip install praxis-ba[tui][/red]")
        raise typer.Exit(1) from None

    app = PraxisApp(engagement_path=eng)
    app.run()
