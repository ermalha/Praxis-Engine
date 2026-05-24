"""Risk subcommands."""

from __future__ import annotations

import json

import typer
from rich.markup import escape as rich_escape
from rich.table import Table

from praxis.cli.errors import handle_praxis_errors
from praxis.engagement import RiskRepo
from praxis.errors import EngagementError

from ._common import _audit_ctx, _resolve_engagement, console, err_console

risk_app = typer.Typer(name="risk", help="Manage the risk register.")


@risk_app.command("list")
@handle_praxis_errors
def risk_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List risks."""
    eng = _resolve_engagement(engagement)
    repo = RiskRepo(eng)
    rlist = repo.list_all()

    if json_output:
        data = [r.model_dump(mode="json") for r in rlist]
        typer.echo(json.dumps(data))
        return

    if not rlist:
        console.print("[dim]No risks.[/dim]")
        return

    table = Table(title="Risks")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Likelihood")
    table.add_column("Impact")
    table.add_column("Status")

    for r in rlist:
        table.add_row(r.id, r.title, r.likelihood, r.impact, r.status)
    console.print(table)


@risk_app.command("add")
@handle_praxis_errors
def risk_add(
    title: str = typer.Argument(..., help="Risk title."),
    description: str = typer.Argument(..., help="Risk description."),
    likelihood: str = typer.Option(..., "--likelihood", "-l", help="low/medium/high"),
    impact: str = typer.Option(..., "--impact", "-i", help="low/medium/high"),
    mitigation: str | None = typer.Option(None, "--mitigation", "-m"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a risk."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = RiskRepo(eng)
        r = repo.add(title, description, likelihood, impact, mitigation=mitigation)
        console.print(f"[green]Added risk {r.title!r} {rich_escape(f'[{r.id}]')}.[/green]")


@risk_app.command("update")
@handle_praxis_errors
def risk_update(
    rid: str = typer.Argument(..., help="Risk ID."),
    status: str | None = typer.Option(None, "--status"),
    mitigation: str | None = typer.Option(None, "--mitigation"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Update a risk."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = RiskRepo(eng)
        kwargs: dict[str, object] = {}
        if status is not None:
            kwargs["status"] = status
        if mitigation is not None:
            kwargs["mitigation"] = mitigation
        if not kwargs:
            err_console.print("[red]No fields to update.[/red]")
            raise typer.Exit(1)
        try:
            r = repo.update(rid, **kwargs)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Updated risk {r.title!r}.[/green]")


@risk_app.command("close")
@handle_praxis_errors
def risk_close(
    rid: str = typer.Argument(..., help="Risk ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Close a risk."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = RiskRepo(eng)
        try:
            r = repo.close(rid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Closed risk {r.title!r}.[/green]")
