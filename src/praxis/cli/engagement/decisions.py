"""Decision (ADR) subcommands."""

from __future__ import annotations

import json

import typer
from rich.markup import escape as rich_escape
from rich.table import Table

from praxis.cli.errors import handle_praxis_errors
from praxis.engagement import DecisionRepo
from praxis.errors import EngagementError

from ._common import _audit_ctx, _resolve_engagement, console, err_console

decision_app = typer.Typer(name="decision", help="Manage architecture decisions.")


@decision_app.command("list")
@handle_praxis_errors
def decision_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all decisions (ADRs)."""
    eng = _resolve_engagement(engagement)
    repo = DecisionRepo(eng)
    dlist = repo.list_all()

    if json_output:
        data = [d.model_dump(mode="json") for d in dlist]
        typer.echo(json.dumps(data))
        return

    if not dlist:
        console.print("[dim]No decisions recorded.[/dim]")
        return

    table = Table(title="Decisions")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Status")

    for d in dlist:
        table.add_row(d.id, d.title, d.status)
    console.print(table)


@decision_app.command("show")
@handle_praxis_errors
def decision_show(
    did: str = typer.Argument(..., help="Decision ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Show a decision record."""
    eng = _resolve_engagement(engagement)
    repo = DecisionRepo(eng)
    result = repo.get(did)
    if result is None:
        err_console.print(f"[red]Decision {did!r} not found.[/red]")
        raise typer.Exit(1)
    fm, body = result
    console.print(f"[bold]{fm.title}[/bold] ({fm.id}) [{fm.status}]")
    console.print(body)


@decision_app.command("new")
@handle_praxis_errors
def decision_new(
    title: str = typer.Argument(..., help="Decision title."),
    context: str = typer.Option(..., "--context", help="Decision context."),
    decision: str = typer.Option(..., "--decision", help="The decision."),
    consequences: str = typer.Option(..., "--consequences", help="Consequences."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Create a new decision record."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = DecisionRepo(eng)
        try:
            d = repo.create(title, context, decision, consequences)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Created decision {rich_escape(d.id)}.[/green]")


@decision_app.command("supersede")
@handle_praxis_errors
def decision_supersede(
    did: str = typer.Argument(..., help="Decision ID to supersede."),
    by: str = typer.Option(..., "--by", help="Superseding decision ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Mark a decision as superseded."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = DecisionRepo(eng)
        try:
            d = repo.supersede(did, by)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        msg = f"Decision {rich_escape(d.id)} superseded by {rich_escape(by)}."
        console.print(f"[green]{msg}[/green]")
