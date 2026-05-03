"""CLI commands: ``praxis email`` — email operations."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from praxis.config.engagement import find_engagement
from praxis.config.loader import load_engagement_config

email_app = typer.Typer(name="email", help="Email integration commands.")
err_console = Console(stderr=True)


@email_app.command("poll")
def email_poll(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """One-shot inbox check — fetch new messages and match replies."""
    eng = Path(engagement) if engagement else find_engagement(Path.cwd())
    if eng is None:
        err_console.print("[red]No engagement found.[/red]")
        raise typer.Exit(1)

    cfg = load_engagement_config(eng)
    imap_cfg = cfg.integrations.get("email")
    if imap_cfg is None or not imap_cfg.enabled:
        err_console.print("[yellow]IMAP integration not enabled.[/yellow]")
        raise typer.Exit(1)

    from praxis.integrations.email.imap_watcher import ImapWatcher
    from praxis.integrations.email.matcher import match_replies

    console = Console()
    state_dir = eng / ".praxis" / "state"
    watcher = ImapWatcher(imap_cfg.settings)
    messages = watcher.fetch_since(state_dir=state_dir)
    console.print(f"Fetched {len(messages)} message(s).")

    matches = match_replies(messages, eng)
    if matches:
        console.print(f"[green]Matched {len(matches)} reply(ies) to work-items.[/green]")
        for msg, item_id in matches:
            console.print(f"  - {msg.subject} -> work-item {item_id}")
    else:
        console.print("[dim]No replies matched open work-items.[/dim]")
