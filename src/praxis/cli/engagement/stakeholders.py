"""Stakeholder subcommands."""

from __future__ import annotations

import json

import typer
from rich.markup import escape as rich_escape
from rich.table import Table

from praxis.cli.errors import handle_praxis_errors
from praxis.engagement import StakeholderRepo
from praxis.errors import EngagementError

from ._common import _audit_ctx, _resolve_engagement, console, err_console

stakeholder_app = typer.Typer(name="stakeholder", help="Manage stakeholders.")


@stakeholder_app.command("list")
@handle_praxis_errors
def stakeholder_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all stakeholders."""
    eng = _resolve_engagement(engagement)
    repo = StakeholderRepo(eng)
    slist = repo.list_all()

    if json_output:
        data = [s.model_dump(mode="json") for s in slist]
        typer.echo(json.dumps(data))
        return

    if not slist:
        console.print("[dim]No stakeholders.[/dim]")
        return

    table = Table(title="Stakeholders")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Role")
    table.add_column("Influence")
    table.add_column("Interest")

    for s in slist:
        table.add_row(s.id, s.name, s.role, s.influence, s.interest)
    console.print(table)


@stakeholder_app.command("get")
@handle_praxis_errors
def stakeholder_get(
    sid: str = typer.Argument(..., help="Stakeholder ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Get a stakeholder by ID."""
    eng = _resolve_engagement(engagement)
    repo = StakeholderRepo(eng)
    s = repo.get(sid)
    if s is None:
        err_console.print(f"[red]Stakeholder {sid!r} not found.[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{s.name}[/bold] — {s.role} {rich_escape(f'[{s.id}]')}")
    if s.expertise:
        console.print(f"Expertise: {', '.join(s.expertise)}")
    if s.decision_authority:
        console.print(f"Decision authority: {', '.join(s.decision_authority)}")


@stakeholder_app.command("add")
@handle_praxis_errors
def stakeholder_add(
    name: str = typer.Argument(..., help="Stakeholder name."),
    role: str = typer.Argument(..., help="Stakeholder role."),
    expertise: str | None = typer.Option(None, "--expertise", help="Comma-separated."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a stakeholder."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = StakeholderRepo(eng)
        exp = [e.strip() for e in expertise.split(",")] if expertise else None
        s = repo.add(name, role, expertise=exp)
        console.print(f"[green]Added stakeholder {s.name!r} {rich_escape(f'[{s.id}]')}.[/green]")


@stakeholder_app.command("update")
@handle_praxis_errors
def stakeholder_update(
    sid: str = typer.Argument(..., help="Stakeholder ID."),
    role: str | None = typer.Option(None, "--role"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Update a stakeholder."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = StakeholderRepo(eng)
        kwargs: dict[str, object] = {}
        if role is not None:
            kwargs["role"] = role
        if not kwargs:
            err_console.print("[red]No fields to update.[/red]")
            raise typer.Exit(1)
        try:
            s = repo.update(sid, **kwargs)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Updated stakeholder {s.name!r}.[/green]")


@stakeholder_app.command("remove")
@handle_praxis_errors
def stakeholder_remove(
    sid: str = typer.Argument(..., help="Stakeholder ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Remove a stakeholder."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = StakeholderRepo(eng)
        try:
            repo.remove(sid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Removed stakeholder {sid!r}.[/green]")
