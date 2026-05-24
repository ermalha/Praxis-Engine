"""Assumption subcommands."""

from __future__ import annotations

import json

import typer
from rich.markup import escape as rich_escape
from rich.table import Table

from praxis.cli.errors import handle_praxis_errors
from praxis.engagement import AssumptionsConstraintsRepo
from praxis.errors import EngagementError

from ._common import _audit_ctx, _resolve_engagement, console, err_console

assumption_app = typer.Typer(name="assumption", help="Manage assumptions.")


@assumption_app.command("list")
@handle_praxis_errors
def assumption_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all assumptions."""
    eng = _resolve_engagement(engagement)
    repo = AssumptionsConstraintsRepo(eng)
    alist = repo.list_assumptions()

    if json_output:
        data = [a.model_dump(mode="json") for a in alist]
        typer.echo(json.dumps(data))
        return

    if not alist:
        console.print("[dim]No assumptions.[/dim]")
        return

    table = Table(title="Assumptions")
    table.add_column("ID", style="dim")
    table.add_column("Statement", style="bold")
    table.add_column("Validated")

    for a in alist:
        validated = "yes" if a.validated else "no"
        table.add_row(a.id, a.statement, validated)
    console.print(table)


@assumption_app.command("add")
@handle_praxis_errors
def assumption_add(
    statement: str = typer.Argument(..., help="Assumption statement."),
    rationale: str | None = typer.Option(None, "--rationale", "-r"),
    validation_method: str | None = typer.Option(None, "--validation-method"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add an assumption."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        a = repo.add_assumption(statement, rationale=rationale, validation_method=validation_method)
        console.print(f"[green]Added assumption {rich_escape(f'[{a.id}]')}.[/green]")


@assumption_app.command("validate")
@handle_praxis_errors
def assumption_validate(
    aid: str = typer.Argument(..., help="Assumption ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Mark an assumption as validated."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        try:
            a = repo.validate_assumption(aid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Validated assumption {rich_escape(f'[{a.id}]')}.[/green]")


@assumption_app.command("invalidate")
@handle_praxis_errors
def assumption_invalidate(
    aid: str = typer.Argument(..., help="Assumption ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Mark an assumption as invalidated."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        try:
            a = repo.invalidate_assumption(aid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Invalidated assumption {rich_escape(f'[{a.id}]')}.[/green]")


@assumption_app.command("get")
@handle_praxis_errors
def assumption_get(
    aid: str = typer.Argument(..., help="Assumption ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show details for a single assumption."""
    eng = _resolve_engagement(engagement)
    repo = AssumptionsConstraintsRepo(eng)
    try:
        a = repo.get_assumption(aid)
    except EngagementError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(json.dumps(a.model_dump(mode="json")))
        return

    console.print(f"[bold]Assumption {rich_escape(f'[{a.id}]')}[/bold]")
    console.print(f"  Statement: {a.statement}")
    if a.rationale:
        console.print(f"  Rationale: {a.rationale}")
    if a.validation_method:
        console.print(f"  Validation method: {a.validation_method}")
    console.print(f"  Validated: {'yes' if a.validated else 'no'}")


@assumption_app.command("update")
@handle_praxis_errors
def assumption_update(
    aid: str = typer.Argument(..., help="Assumption ID."),
    statement: str | None = typer.Option(None, "--statement"),
    rationale: str | None = typer.Option(None, "--rationale", "-r"),
    validation_method: str | None = typer.Option(None, "--validation-method"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Update mutable fields on an assumption. Only supplied flags are written."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        try:
            a = repo.update_assumption(
                aid,
                statement=statement,
                rationale=rationale,
                validation_method=validation_method,
            )
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Updated assumption {rich_escape(f'[{a.id}]')}.[/green]")


@assumption_app.command("remove")
@handle_praxis_errors
def assumption_remove(
    aid: str = typer.Argument(..., help="Assumption ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Remove an assumption."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        try:
            repo.remove_assumption(aid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Removed assumption {rich_escape(f'[{aid}]')}.[/green]")
