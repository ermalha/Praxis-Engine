"""System-landscape subcommands."""

from __future__ import annotations

import json

import typer
from rich.markup import escape as rich_escape
from rich.table import Table

from praxis.cli.errors import handle_praxis_errors
from praxis.engagement import SystemLandscapeRepo

from ._common import _audit_ctx, _resolve_engagement, console, err_console

system_app = typer.Typer(name="system", help="Manage the system landscape.")


@system_app.command("list")
@handle_praxis_errors
def system_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List systems."""
    eng = _resolve_engagement(engagement)
    repo = SystemLandscapeRepo(eng)
    slist = repo.list_all()

    if json_output:
        data = [s.model_dump(mode="json") for s in slist]
        typer.echo(json.dumps(data))
        return

    if not slist:
        console.print("[dim]No systems.[/dim]")
        return

    table = Table(title="Systems")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Kind")
    table.add_column("Status")

    for s in slist:
        table.add_row(s.id, s.name, s.kind, s.status)
    console.print(table)


@system_app.command("add")
@handle_praxis_errors
def system_add(
    name: str = typer.Argument(..., help="System name."),
    kind: str = typer.Argument(..., help="System kind (e.g. web app, API)."),
    description: str | None = typer.Option(None, "--description", "-d"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a system."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = SystemLandscapeRepo(eng)
        s = repo.add(name, kind, description=description)
        console.print(f"[green]Added system {s.name!r} {rich_escape(f'[{s.id}]')}.[/green]")


@system_app.command("show")
@handle_praxis_errors
def system_show(
    sid: str = typer.Argument(..., help="System ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Show a system."""
    eng = _resolve_engagement(engagement)
    repo = SystemLandscapeRepo(eng)
    s = repo.get(sid)
    if s is None:
        err_console.print(f"[red]System {sid!r} not found.[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{s.name}[/bold] ({s.kind}) {rich_escape(f'[{s.id}]')}")
    if s.description:
        console.print(f"Description: {s.description}")
    console.print(f"Status: {s.status}")
