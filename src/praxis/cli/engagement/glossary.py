"""Glossary subcommands."""

from __future__ import annotations

import json

import typer
from rich.table import Table

from praxis.cli.errors import handle_praxis_errors
from praxis.engagement import GlossaryRepo
from praxis.errors import EngagementError

from ._common import _audit_ctx, _resolve_engagement, console, err_console

glossary_app = typer.Typer(name="glossary", help="Manage the engagement glossary.")


@glossary_app.command("list")
@handle_praxis_errors
def glossary_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all glossary terms."""
    eng = _resolve_engagement(engagement)
    repo = GlossaryRepo(eng)
    glossary = repo.load()

    if json_output:
        data = [t.model_dump(mode="json") for t in glossary.terms]
        typer.echo(json.dumps(data))
        return

    if not glossary.terms:
        console.print("[dim]No glossary terms.[/dim]")
        return

    table = Table(title="Glossary")
    table.add_column("Term", style="bold")
    table.add_column("Definition")
    table.add_column("Synonyms")

    for t in glossary.terms:
        table.add_row(t.term, t.definition, ", ".join(t.synonyms) or "-")
    console.print(table)


@glossary_app.command("get")
@handle_praxis_errors
def glossary_get(
    term: str = typer.Argument(..., help="Term to look up."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Get a specific glossary term."""
    eng = _resolve_engagement(engagement)
    repo = GlossaryRepo(eng)
    t = repo.get(term)
    if t is None:
        err_console.print(f"[red]Term {term!r} not found.[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{t.term}[/bold]: {t.definition}")
    if t.synonyms:
        console.print(f"Synonyms: {', '.join(t.synonyms)}")
    if t.notes:
        console.print(f"Notes: {t.notes}")


@glossary_app.command("search")
@handle_praxis_errors
def glossary_search(
    query: str = typer.Argument(..., help="Search query."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Search glossary terms."""
    eng = _resolve_engagement(engagement)
    repo = GlossaryRepo(eng)
    matches = repo.find(query)
    if not matches:
        console.print(f"[dim]No terms match {query!r}.[/dim]")
        return
    for t in matches:
        console.print(f"- [bold]{t.term}[/bold]: {t.definition}")


@glossary_app.command("add")
@handle_praxis_errors
def glossary_add(
    term: str = typer.Argument(..., help="Term name."),
    definition: str = typer.Argument(..., help="Term definition."),
    synonyms: str | None = typer.Option(None, "--synonyms", "-s", help="Comma-separated."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a glossary term."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = GlossaryRepo(eng)
        syn = [s.strip() for s in synonyms.split(",")] if synonyms else None
        try:
            t = repo.add_term(term, definition, synonyms=syn)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Added term {t.term!r}.[/green]")


@glossary_app.command("remove")
@handle_praxis_errors
def glossary_remove(
    term: str = typer.Argument(..., help="Term to remove."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Remove a glossary term."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = GlossaryRepo(eng)
        try:
            repo.remove_term(term)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Removed term {term!r}.[/green]")
