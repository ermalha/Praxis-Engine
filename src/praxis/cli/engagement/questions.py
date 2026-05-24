"""Open-question subcommands."""

from __future__ import annotations

import json

import typer
from rich.markup import escape as rich_escape
from rich.table import Table

from praxis.cli.errors import handle_praxis_errors
from praxis.engagement import OpenQuestionsRepo
from praxis.errors import EngagementError

from ._common import _audit_ctx, _resolve_engagement, console, err_console

question_app = typer.Typer(name="question", help="Manage open questions.")


@question_app.command("list")
@handle_praxis_errors
def question_list(
    status: str | None = typer.Option(None, "--status", "-s"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List open questions."""
    eng = _resolve_engagement(engagement)
    repo = OpenQuestionsRepo(eng)
    qlist = repo.list_all(status=status)

    if json_output:
        data = [q.model_dump(mode="json") for q in qlist]
        typer.echo(json.dumps(data))
        return

    if not qlist:
        console.print("[dim]No questions.[/dim]")
        return

    table = Table(title="Questions")
    table.add_column("ID", style="dim")
    table.add_column("Question", style="bold")
    table.add_column("Status")
    table.add_column("Priority")

    for q in qlist:
        table.add_row(q.id, q.question, q.status, q.priority)
    console.print(table)


@question_app.command("open")
@handle_praxis_errors
def question_open(
    question: str = typer.Argument(..., help="The question."),
    why: str = typer.Option(..., "--why", help="Why it matters."),
    priority: str = typer.Option("medium", "--priority", "-p"),
    answerers: str | None = typer.Option(
        None,
        "--answerers",
        help="Comma-separated stakeholder IDs who could answer this.",
    ),
    blocks: str | None = typer.Option(
        None,
        "--blocks",
        help="Comma-separated artifact IDs this question blocks.",
    ),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Open a new tracked question."""
    eng = _resolve_engagement(engagement)
    candidate_answerers = (
        [s.strip() for s in answerers.split(",") if s.strip()] if answerers else None
    )
    blocked_artifacts = [b.strip() for b in blocks.split(",") if b.strip()] if blocks else None
    with _audit_ctx(eng):
        repo = OpenQuestionsRepo(eng)
        try:
            q = repo.open(
                question,
                why,
                priority=priority,
                candidate_answerers=candidate_answerers,
                blocks=blocked_artifacts,
            )
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Opened question {rich_escape(q.id)}.[/green]")


@question_app.command("answer")
@handle_praxis_errors
def question_answer(
    qid: str = typer.Argument(..., help="Question ID."),
    answer: str = typer.Argument(..., help="The answer."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Answer a question."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = OpenQuestionsRepo(eng)
        try:
            q = repo.answer(qid, answer)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Answered question {rich_escape(q.id)}.[/green]")


@question_app.command("withdraw")
@handle_praxis_errors
def question_withdraw(
    qid: str = typer.Argument(..., help="Question ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Withdraw a question."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = OpenQuestionsRepo(eng)
        try:
            q = repo.withdraw(qid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Withdrew question {rich_escape(q.id)}.[/green]")
