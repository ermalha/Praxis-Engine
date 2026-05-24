"""Timeline / milestone subcommands."""

from __future__ import annotations

import json
from datetime import date

import typer
from rich.markup import escape as rich_escape
from rich.table import Table

from praxis.cli.errors import handle_praxis_errors
from praxis.engagement import TimelineRepo
from praxis.errors import EngagementError

from ._common import _audit_ctx, _resolve_engagement, console, err_console

timeline_app = typer.Typer(name="timeline", help="Manage project milestones.")


@timeline_app.command("list")
@handle_praxis_errors
def timeline_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List milestones."""
    eng = _resolve_engagement(engagement)
    repo = TimelineRepo(eng)
    mlist = repo.list_all()

    if json_output:
        data = [m.model_dump(mode="json") for m in mlist]
        typer.echo(json.dumps(data))
        return

    if not mlist:
        console.print("[dim]No milestones.[/dim]")
        return

    table = Table(title="Timeline")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Target Date")
    table.add_column("Status")

    for m in mlist:
        table.add_row(m.id, m.title, str(m.target_date), m.status)
    console.print(table)


@timeline_app.command("add")
@handle_praxis_errors
def timeline_add(
    title: str = typer.Argument(..., help="Milestone title."),
    target_date: str = typer.Option(..., "--date", "-d", help="Target date (YYYY-MM-DD)."),
    notes: str | None = typer.Option(None, "--notes"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a milestone."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = TimelineRepo(eng)
        d = date.fromisoformat(target_date)
        m = repo.add(title, d, notes=notes)
        console.print(f"[green]Added milestone {m.title!r} {rich_escape(f'[{m.id}]')}.[/green]")


@timeline_app.command("update")
@handle_praxis_errors
def timeline_update(
    mid: str = typer.Argument(..., help="Milestone ID."),
    status: str | None = typer.Option(None, "--status"),
    target_date: str | None = typer.Option(None, "--date", "-d"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Update a milestone."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = TimelineRepo(eng)
        kwargs: dict[str, object] = {}
        if status is not None:
            kwargs["status"] = status
        if target_date is not None:
            kwargs["target_date"] = date.fromisoformat(target_date)
        if not kwargs:
            err_console.print("[red]No fields to update.[/red]")
            raise typer.Exit(1)
        try:
            m = repo.update(mid, **kwargs)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Updated milestone {m.title!r}.[/green]")
