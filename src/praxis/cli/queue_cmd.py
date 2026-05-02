"""CLI commands: ``praxis queue`` — manage the work-queue."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from praxis.config.engagement import find_engagement
from praxis.workqueue import (
    WorkItemStatus,
    WorkQueueRepo,
    prioritize,
)

console = Console()
err_console = Console(stderr=True)

queue_app = typer.Typer(name="queue", help="Manage the human work-queue.")


def _resolve_eng(engagement: str | None) -> Path:
    eng = Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    if eng is None:
        err_console.print("[red]No engagement found.[/red]")
        raise typer.Exit(1)
    return eng


@queue_app.callback(invoke_without_command=True)
def queue_default(
    ctx: typer.Context,
    all_items: bool = typer.Option(False, "--all", help="Show all items."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show prioritized work-queue (default: human items only)."""
    if ctx.invoked_subcommand is not None:
        return

    eng = _resolve_eng(engagement)
    repo = WorkQueueRepo(eng)
    items = repo.list(limit=100)

    if not all_items:
        items = [i for i in items if i.assignee == "human"]

    ordered = prioritize(items, active_only=not all_items)

    if output_json:
        console.print(
            json.dumps([i.model_dump(mode="json") for i in ordered], indent=2, default=str)
        )
        return

    if not ordered:
        console.print("[dim]No work-items.[/dim]")
        return

    table = Table(title="Work Queue")
    table.add_column("ID", style="dim", width=14)
    table.add_column("Priority", width=10)
    table.add_column("Status", width=12)
    table.add_column("Assignee", width=8)
    table.add_column("Title")

    priority_style = {
        "critical": "[red]CRITICAL[/red]",
        "high": "[yellow]HIGH[/yellow]",
        "medium": "MEDIUM",
        "low": "[dim]LOW[/dim]",
    }

    for item in ordered:
        table.add_row(
            item.id,
            priority_style.get(item.priority.value, item.priority.value),
            item.status.value,
            item.assignee,
            item.title,
        )
    console.print(table)


@queue_app.command("show")
def queue_show(
    item_id: str = typer.Argument(..., help="Work-item ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Show full details of a work-item."""
    eng = _resolve_eng(engagement)
    repo = WorkQueueRepo(eng)
    item = repo.get(item_id)
    if item is None:
        err_console.print(f"[red]Work-item not found: {item_id}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]ID:[/bold] {item.id}")
    console.print(f"[bold]Type:[/bold] {item.type.value}")
    console.print(f"[bold]Status:[/bold] {item.status.value}")
    console.print(f"[bold]Priority:[/bold] {item.priority.value}")
    console.print(f"[bold]Assignee:[/bold] {item.assignee}")
    console.print(f"[bold]Title:[/bold] {item.title}")
    console.print(f"[bold]Description:[/bold] {item.description}")
    console.print(f"[bold]Rationale:[/bold] {item.rationale}")
    if item.deadline:
        console.print(f"[bold]Deadline:[/bold] {item.deadline}")
    if item.completion_note:
        console.print(f"[bold]Note:[/bold] {item.completion_note}")
    if item.return_payload:
        console.print(f"[bold]Return data:[/bold] {json.dumps(item.return_payload, indent=2)}")
    console.print()


@queue_app.command("start")
def queue_start(
    item_id: str = typer.Argument(...),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Mark a work-item as in-progress."""
    eng = _resolve_eng(engagement)
    repo = WorkQueueRepo(eng)
    item = repo.transition(item_id, WorkItemStatus.IN_PROGRESS)
    console.print(f"[green]Started:[/green] {item.id} — {item.title}")


@queue_app.command("done")
def queue_done(
    item_id: str = typer.Argument(...),
    note: str = typer.Option(..., "--note", "-n", help="What happened."),
    return_data: str | None = typer.Option(None, "--return-data"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Mark a work-item as done."""
    eng = _resolve_eng(engagement)
    repo = WorkQueueRepo(eng)
    rp = json.loads(return_data) if return_data else None
    item = repo.transition(item_id, WorkItemStatus.DONE, note=note, return_payload=rp)
    console.print(f"[green]Done:[/green] {item.id} — {item.title}")


@queue_app.command("commit")
def queue_commit(
    item_id: str = typer.Argument(...),
    note: str = typer.Option("Committed", "--note", "-n"),
    result: str | None = typer.Option(None, "--result"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Commit a work-item (start → done in one step, or done from in_progress)."""
    eng = _resolve_eng(engagement)
    repo = WorkQueueRepo(eng)
    item = repo.get(item_id)
    if item is None:
        err_console.print(f"[red]Not found: {item_id}[/red]")
        raise typer.Exit(1)

    rp = json.loads(result) if result else None

    # If queued, start first
    if item.status == WorkItemStatus.QUEUED:
        repo.transition(item_id, WorkItemStatus.IN_PROGRESS)

    item = repo.transition(item_id, WorkItemStatus.DONE, note=note, return_payload=rp)

    # If linked to questions and has return_payload with "answer", update question
    if rp and "answer" in rp and item.related_question_ids:
        _update_linked_questions(eng, item.related_question_ids, str(rp["answer"]))

    console.print(f"[green]Committed:[/green] {item.id} — {item.title}")


@queue_app.command("reject")
def queue_reject(
    item_id: str = typer.Argument(...),
    note: str = typer.Option("Rejected", "--note", "-n"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Reject a work-item."""
    eng = _resolve_eng(engagement)
    repo = WorkQueueRepo(eng)
    item = repo.transition(item_id, WorkItemStatus.REJECTED, note=note)
    console.print(f"[red]Rejected:[/red] {item.id}")


@queue_app.command("defer")
def queue_defer(
    item_id: str = typer.Argument(...),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Defer a work-item."""
    eng = _resolve_eng(engagement)
    repo = WorkQueueRepo(eng)
    item = repo.transition(item_id, WorkItemStatus.DEFERRED)
    console.print(f"[yellow]Deferred:[/yellow] {item.id}")


def _update_linked_questions(
    eng: Path,
    question_ids: list[str],
    answer: str,
) -> None:
    """Update linked OpenQuestions with the answer."""
    import contextlib

    from praxis.engagement import OpenQuestionsRepo

    repo = OpenQuestionsRepo(eng)
    for qid in question_ids:
        with contextlib.suppress(Exception):
            repo.answer(qid, answer)
