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
from praxis.config.profiles import get_active_profile_name
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


def _make_orchestrator(eng: Path, profile_name: str | None = None) -> Orchestrator:
    """Build an Orchestrator with stub agent (for CLI-driven wakes)."""
    from praxis.config.loader import load_engagement_config, load_profile
    from praxis.core.orchestrator import Orchestrator

    eng_config = load_engagement_config(eng)
    resolved_name = profile_name or get_active_profile_name()
    profile = load_profile(resolved_name)

    return Orchestrator(
        agent=None,
        profile=profile,
        engagement=eng_config,
        engagement_path=eng,
    )


def run(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
) -> None:
    """Start the orchestrator — runs continuously until Ctrl-C."""
    eng = _resolve_eng(engagement)

    orch = _make_orchestrator(eng, profile_name=profile)
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
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile name."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan tasks but don't execute."),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Run a single wake cycle."""
    eng = _resolve_eng(engagement)
    orch = _make_orchestrator(eng, profile_name=profile)

    report = orch.wake_once(trigger=WakeTrigger.MANUAL, dry_run=dry_run)

    if output_json:
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
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
        typer.echo(json.dumps(plan.model_dump(mode="json"), indent=2, default=str))
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
    import contextlib

    eng = _resolve_eng(engagement)

    from praxis.config.loader import load_engagement_config
    from praxis.engagement.repos.assumptions import AssumptionsConstraintsRepo
    from praxis.engagement.repos.decisions import DecisionRepo
    from praxis.engagement.repos.glossary import GlossaryRepo
    from praxis.engagement.repos.questions import OpenQuestionsRepo
    from praxis.engagement.repos.risks import RiskRepo
    from praxis.engagement.repos.stakeholders import StakeholderRepo
    from praxis.workqueue import WorkQueueRepo

    # D-040: real engagement name from config (eng is the dir Path)
    eng_name = eng.name
    with contextlib.suppress(Exception):
        eng_name = load_engagement_config(eng).name

    # Gather state
    q_repo = OpenQuestionsRepo(eng)
    questions = q_repo.list_all()
    open_qs = [q for q in questions if q.status in ("open", "asked")]
    critical_open = sorted(
        [q for q in open_qs if q.priority == "critical"],
        key=lambda q: q.created_at,
    )[:3]

    stakeholders = StakeholderRepo(eng).list_all()
    glossary = GlossaryRepo(eng).load().terms
    decisions = DecisionRepo(eng).list_all()
    ac_repo = AssumptionsConstraintsRepo(eng)
    constraints = ac_repo.list_constraints()
    assumptions = ac_repo.list_assumptions()
    risks = RiskRepo(eng).list_all()

    wq_repo = WorkQueueRepo(eng)
    all_items = wq_repo.list(limit=200)
    human_items = [i for i in all_items if i.assignee == "human"]
    agent_items = [i for i in all_items if i.assignee == "agent"]
    human_active = [i for i in human_items if i.status.value in ("queued", "in_progress")]
    agent_active = [i for i in agent_items if i.status.value in ("queued", "in_progress")]

    # Last wake report
    reports_dir = eng / ".praxis" / "state" / "wake-reports"
    last_wake = None
    if reports_dir.exists():
        files = sorted(reports_dir.glob("*.json"), reverse=True)
        if files:
            with contextlib.suppress(json.JSONDecodeError, OSError):
                last_wake = json.loads(files[0].read_text(encoding="utf-8"))

    # Last sufficiency report (newest by generated_at; mtime fallback)
    suff_dir = eng / ".praxis" / "state" / "sufficiency-reports"
    last_sufficiency: dict[str, object] | None = None
    if suff_dir.is_dir():
        best: tuple[str, dict[str, object]] | None = None
        for f in suff_dir.glob("*.json"):
            with contextlib.suppress(json.JSONDecodeError, OSError, KeyError):
                data = json.loads(f.read_text(encoding="utf-8"))
                sort_key = str(data.get("generated_at") or f.stat().st_mtime)
                if best is None or sort_key > best[0]:
                    best = (sort_key, data)
        if best is not None:
            last_sufficiency = {
                "verdict": best[1].get("verdict"),
                "generated_at": best[1].get("generated_at"),
                "artifact_kind": best[1].get("artifact_kind"),
                "artifact_target": best[1].get("artifact_target"),
            }

    if output_json:
        data = {
            "name": eng_name,
            "stakeholders": len(stakeholders),
            "glossary": len(glossary),
            "decisions": len(decisions),
            "constraints": len(constraints),
            "assumptions": len(assumptions),
            "risks": len(risks),
            "questions_open": len(open_qs),
            "questions_total": len(questions),
            "workitems_human_active": len(human_active),
            "workitems_human_total": len(human_items),
            "workitems_agent_active": len(agent_active),
            "workitems_agent_total": len(agent_items),
            "last_wake": last_wake,
            "last_sufficiency": last_sufficiency,
        }
        typer.echo(json.dumps(data, indent=2, default=str))
        return

    console.print(f"\n[bold]Engagement Status:[/bold] {eng_name}")

    table = Table()
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Stakeholders", str(len(stakeholders)))
    table.add_row("Glossary terms", str(len(glossary)))
    table.add_row("Decisions", str(len(decisions)))
    table.add_row("Constraints", str(len(constraints)))
    table.add_row("Assumptions", str(len(assumptions)))
    table.add_row("Risks", str(len(risks)))
    table.add_row("Open questions", f"{len(open_qs)} / {len(questions)}")
    table.add_row("Human work-items (active/total)", f"{len(human_active)} / {len(human_items)}")
    table.add_row("Agent work-items (active/total)", f"{len(agent_active)} / {len(agent_items)}")

    if last_sufficiency:
        verdict = last_sufficiency.get("verdict") or "?"
        when = last_sufficiency.get("generated_at") or "?"
        table.add_row("Last sufficiency", f"{verdict} ({when})")
    if last_wake:
        table.add_row("Last wake", last_wake.get("started_at", "?"))

    console.print(table)

    if critical_open:
        from rich.markup import escape as rich_escape

        console.print("\n[bold]Top critical open questions:[/bold]")
        for q in critical_open:
            console.print(f"  - {rich_escape(f'[{q.id}]')} {rich_escape(q.question)}")
    console.print()
