"""CLI commands: ``praxis run``, ``praxis wake``, ``praxis plan``, ``praxis status``."""

from __future__ import annotations

import json
import signal
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from praxis.config.engagement import find_engagement
from praxis.core.wake.models import WakeTrigger

if TYPE_CHECKING:
    from praxis.core.orchestrator import Orchestrator

console = Console()
err_console = Console(stderr=True)


def _resolve_eng(engagement: str | None) -> Path:
    eng = Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    if eng is None:
        err_console.print("[red]No engagement found.[/red]")
        raise typer.Exit(1)
    return eng


def _make_orchestrator(eng: Path) -> Orchestrator:
    """Build an Orchestrator with stub agent (for CLI-driven wakes)."""
    from praxis.config.loader import load_engagement_config, load_profile
    from praxis.core.orchestrator import Orchestrator

    eng_config = load_engagement_config(eng)
    profile = load_profile("default")

    return Orchestrator(
        agent=None,  # type: ignore[arg-type]
        profile=profile,
        engagement=eng_config,
        engagement_path=eng,
    )


def run(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Start the orchestrator — runs continuously until Ctrl-C."""
    eng = _resolve_eng(engagement)

    orch = _make_orchestrator(eng)
    cancel = threading.Event()

    def _on_sigint(_sig: int, _frame: object) -> None:
        console.print("\n[yellow]Shutting down orchestrator...[/yellow]")
        cancel.set()

    signal.signal(signal.SIGINT, _on_sigint)

    console.print(f"[green]Starting orchestrator[/green] for {eng.name}")
    try:
        orch.run_forever(cancel_event=cancel)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]Orchestrator error:[/red] {exc}")
        raise typer.Exit(1) from None
    console.print("[dim]Orchestrator stopped.[/dim]")


def wake(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan tasks but don't execute."),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Run a single wake cycle."""
    eng = _resolve_eng(engagement)
    orch = _make_orchestrator(eng)

    report = orch.wake_once(trigger=WakeTrigger.MANUAL, dry_run=dry_run)

    if output_json:
        console.print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
        return

    console.print(f"\n[bold]Wake Report[/bold] ({report.trigger.value})")
    console.print(f"  Duration: {report.started_at} → {report.ended_at}")
    if report.notes:
        console.print(f"  Notes: {report.notes}")

    if report.tasks_considered:
        console.print(f"\n  Tasks considered: {len(report.tasks_considered)}")
    if report.tasks_executed:
        console.print(f"  Tasks executed: {len(report.tasks_executed)}")
        for t in report.tasks_executed:
            console.print(f"    - {t}")
    if report.workitems_created:
        console.print(f"  Work-items created: {', '.join(report.workitems_created)}")
    console.print()


def plan_today(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Generate today's daily plan."""
    eng = _resolve_eng(engagement)

    from praxis.core.wake.daily_plan import generate_daily_plan

    plan = generate_daily_plan(eng)

    if output_json:
        console.print(json.dumps(plan.model_dump(mode="json"), indent=2, default=str))
        return

    console.print(f"\n[bold]Daily Plan — {plan.date}[/bold]")
    console.print(plan.summary)

    if plan.top_workitems:
        console.print("\n[bold]Top Items:[/bold]")
        for item in plan.top_workitems:
            console.print(f"  - {item}")

    if plan.open_blockers:
        console.print("\n[bold]Blockers:[/bold]")
        for b in plan.open_blockers:
            console.print(f"  - [red]{b}[/red]")

    if plan.recent_activity:
        console.print("\n[bold]Recent Activity:[/bold]")
        for a in plan.recent_activity:
            console.print(f"  - {a}")
    console.print()


plan_app = typer.Typer(name="plan", help="Generate planning artifacts.")
plan_app.command("today")(plan_today)


def status(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show engagement health snapshot."""
    eng = _resolve_eng(engagement)

    from praxis.engagement.repos.questions import OpenQuestionsRepo
    from praxis.engagement.repos.stakeholders import StakeholderRepo
    from praxis.workqueue import WorkQueueRepo, prioritize

    # Gather data
    q_repo = OpenQuestionsRepo(eng)
    s_repo = StakeholderRepo(eng)
    wq_repo = WorkQueueRepo(eng)

    questions = q_repo.list_all()
    stakeholders = s_repo.list_all()
    all_items = wq_repo.list(limit=100)
    human_items = [i for i in all_items if i.assignee == "human"]
    active = [i for i in human_items if i.status.value in ("queued", "in_progress")]
    ordered = prioritize(active, active_only=True)[:5]

    # Recent wake report
    import contextlib

    reports_dir = eng / ".praxis" / "state" / "wake-reports"
    last_wake = None
    if reports_dir.exists():
        files = sorted(reports_dir.glob("*.json"), reverse=True)
        if files:
            with contextlib.suppress(json.JSONDecodeError, OSError):
                last_wake = json.loads(files[0].read_text(encoding="utf-8"))

    if output_json:
        data = {
            "stakeholders": len(stakeholders),
            "questions_open": len([q for q in questions if q.status in ("open", "asked")]),
            "questions_total": len(questions),
            "workitems_active": len(active),
            "workitems_total": len(all_items),
            "last_wake": last_wake,
        }
        console.print(json.dumps(data, indent=2, default=str))
        return

    console.print(f"\n[bold]Engagement Status:[/bold] {eng.name}")

    table = Table()
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Stakeholders", str(len(stakeholders)))
    open_qs = [q for q in questions if q.status in ("open", "asked")]
    table.add_row("Open questions", f"{len(open_qs)} / {len(questions)}")
    table.add_row("Active work-items", f"{len(active)} / {len(all_items)}")

    if last_wake:
        table.add_row("Last wake", last_wake.get("started_at", "?"))

    console.print(table)

    if ordered:
        console.print("\n[bold]Top queue items:[/bold]")
        for item in ordered:
            console.print(f"  - [{item.priority.value.upper()}] {item.title}")
    console.print()
