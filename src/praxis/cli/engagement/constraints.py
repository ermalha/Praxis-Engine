"""Constraint subcommands."""

from __future__ import annotations

import json

import typer
from rich.markup import escape as rich_escape
from rich.table import Table

from praxis.cli.errors import handle_praxis_errors
from praxis.engagement import AssumptionsConstraintsRepo
from praxis.errors import EngagementError

from ._common import _audit_ctx, _resolve_engagement, console, err_console

constraint_app = typer.Typer(name="constraint", help="Manage constraints.")


@constraint_app.command("list")
@handle_praxis_errors
def constraint_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all constraints."""
    eng = _resolve_engagement(engagement)
    repo = AssumptionsConstraintsRepo(eng)
    clist = repo.list_constraints()

    if json_output:
        data = [c.model_dump(mode="json") for c in clist]
        typer.echo(json.dumps(data))
        return

    if not clist:
        console.print("[dim]No constraints.[/dim]")
        return

    table = Table(title="Constraints")
    table.add_column("ID", style="dim")
    table.add_column("Statement", style="bold")
    table.add_column("Type")
    table.add_column("Source")

    for c in clist:
        table.add_row(c.id, c.statement, c.constraint_type, c.source or "-")
    console.print(table)


@constraint_app.command("add")
@handle_praxis_errors
def constraint_add(
    statement: str = typer.Argument(..., help="Constraint statement."),
    constraint_type: str = typer.Argument(..., help="Type (technical, business, regulatory)."),
    source: str | None = typer.Option(None, "--source", "-s"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a constraint."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        c = repo.add_constraint(statement, constraint_type, source=source)
        console.print(f"[green]Added constraint {rich_escape(f'[{c.id}]')}.[/green]")


@constraint_app.command("get")
@handle_praxis_errors
def constraint_get(
    cid: str = typer.Argument(..., help="Constraint ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show details for a single constraint."""
    eng = _resolve_engagement(engagement)
    repo = AssumptionsConstraintsRepo(eng)
    try:
        c = repo.get_constraint(cid)
    except EngagementError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(json.dumps(c.model_dump(mode="json")))
        return

    console.print(f"[bold]Constraint {rich_escape(f'[{c.id}]')}[/bold]")
    console.print(f"  Statement: {c.statement}")
    console.print(f"  Type: {c.constraint_type}")
    console.print(f"  Source: {c.source or '-'}")


@constraint_app.command("update")
@handle_praxis_errors
def constraint_update(
    cid: str = typer.Argument(..., help="Constraint ID."),
    statement: str | None = typer.Option(None, "--statement"),
    constraint_type: str | None = typer.Option(None, "--type"),
    source: str | None = typer.Option(None, "--source", "-s"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Update mutable fields on a constraint. Only supplied flags are written."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        try:
            c = repo.update_constraint(
                cid,
                statement=statement,
                constraint_type=constraint_type,
                source=source,
            )
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Updated constraint {rich_escape(f'[{c.id}]')}.[/green]")


@constraint_app.command("remove")
@handle_praxis_errors
def constraint_remove(
    cid: str = typer.Argument(..., help="Constraint ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Remove a constraint."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        try:
            repo.remove_constraint(cid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Removed constraint {rich_escape(f'[{cid}]')}.[/green]")
