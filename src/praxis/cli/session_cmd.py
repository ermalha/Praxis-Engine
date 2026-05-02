"""CLI commands for session management."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from praxis.config.engagement import find_engagement
from praxis.core.session import get_session, list_sessions
from praxis.storage.repos.messages import MessageRepo

console = Console()
err_console = Console(stderr=True)

session_app = typer.Typer(name="sessions", help="Manage chat sessions.")


def _resolve_db(engagement: str | None) -> Path:
    """Resolve the DB path from engagement."""
    eng = Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    if eng is None:
        err_console.print("[red]No engagement found.[/red]")
        raise typer.Exit(1)
    db_path = eng / ".praxis" / "state" / "praxis.db"
    if not db_path.exists():
        err_console.print("[red]No database found.[/red]")
        raise typer.Exit(1)
    return db_path


@session_app.command("list")
def sessions_list(
    limit: int = typer.Option(20, "--limit", "-n"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """List recent sessions."""
    db_path = _resolve_db(engagement)
    sessions = list_sessions(db_path, limit=limit)

    if not sessions:
        console.print("[dim]No sessions.[/dim]")
        return

    table = Table(title="Sessions")
    table.add_column("ID", style="dim")
    table.add_column("Started")
    table.add_column("Status")
    table.add_column("Summary")

    for s in sessions:
        status = "[green]ended[/green]" if s.ended_at else "[yellow]active[/yellow]"
        summary = s.summary or "-"
        table.add_row(s.id[:12] + "…", str(s.started_at)[:19], status, summary)
    console.print(table)


@session_app.command("show")
def sessions_show(
    session_id: str = typer.Argument(..., help="Session ID (or prefix)."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Show messages from a session."""
    db_path = _resolve_db(engagement)

    # Try exact match first, then prefix match
    session = get_session(db_path, session_id)
    if session is None:
        # Try prefix match
        all_sessions = list_sessions(db_path, limit=100)
        matches = [s for s in all_sessions if s.id.startswith(session_id)]
        if len(matches) == 1:
            session = matches[0]
        elif len(matches) > 1:
            err_console.print(f"[red]Ambiguous prefix. Matches: {len(matches)}[/red]")
            raise typer.Exit(1)
        else:
            err_console.print(f"[red]Session not found: {session_id}[/red]")
            raise typer.Exit(1)

    console.print(f"[bold]Session:[/bold] {session.id}")
    console.print(f"[bold]Started:[/bold] {session.started_at}")
    if session.ended_at:
        console.print(f"[bold]Ended:[/bold] {session.ended_at}")
    if session.summary:
        console.print(f"[bold]Summary:[/bold] {session.summary}")

    repo = MessageRepo(db_path)
    messages = repo.list_by_session(session.id)
    console.print(f"\n[dim]{len(messages)} messages:[/dim]\n")

    for msg in messages:
        role_style = {
            "user": "bold blue",
            "assistant": "bold green",
            "tool": "dim",
            "system": "dim yellow",
        }.get(msg.role.value, "")
        console.print(f"[{role_style}]{msg.role.value}[/{role_style}]: {msg.content[:200]}")
