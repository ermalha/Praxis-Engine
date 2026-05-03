"""CLI commands: ``praxis webhook`` — webhook server."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from praxis.config.engagement import find_engagement
from praxis.config.loader import load_engagement_config

webhook_app = typer.Typer(name="webhook", help="Manage webhook receiver.")
err_console = Console(stderr=True)


@webhook_app.command("serve")
def webhook_serve(
    port: int = typer.Option(8765, "--port", "-p", help="Port to listen on."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Start the webhook receiver server."""
    eng = Path(engagement) if engagement else find_engagement(Path.cwd())
    if eng is None:
        err_console.print("[red]No engagement found.[/red]")
        raise typer.Exit(1)

    cfg = load_engagement_config(eng)
    webhook_cfg = cfg.integrations.get("webhook")
    settings = webhook_cfg.settings if webhook_cfg else {}
    settings["port"] = str(port)

    from praxis.integrations.webhook.server import serve

    serve(settings, eng)
