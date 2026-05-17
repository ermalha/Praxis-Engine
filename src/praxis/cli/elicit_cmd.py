"""CLI command: ``praxis elicit`` — plan elicitations from a sufficiency report."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from praxis.config.engagement import find_engagement
from praxis.config.loader import load_profile, resolve_model_config
from praxis.config.profiles import get_active_profile_name
from praxis.transport.factory import make_transport

console = Console()
err_console = Console(stderr=True)


def elicit(
    report_id: str = typer.Argument(None, help="Sufficiency report ID (or prefix). Use --latest."),
    latest: bool = typer.Option(False, "--latest", help="Use the latest report."),
    profile: str | None = typer.Option(None, "--profile", "-p"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    model_alias: str | None = typer.Option(None, "--model", "-m"),
    max_drafts: int = typer.Option(5, "--max-drafts", "-n"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Plan elicitation drafts from a sufficiency report."""
    eng_path: Path | None = (
        Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    )
    if eng_path is None:
        err_console.print("[red]No engagement found.[/red]")
        raise typer.Exit(1)

    reports_dir = eng_path / ".praxis" / "state" / "sufficiency-reports"

    # Find the report
    if latest:
        reports = sorted(reports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not reports:
            err_console.print("[red]No sufficiency reports found.[/red]")
            raise typer.Exit(1)
        report_path = reports[-1]
    elif report_id:
        report_path = reports_dir / f"{report_id}.json"
        if not report_path.is_file():
            matches = list(reports_dir.glob(f"{report_id}*.json"))
            if len(matches) == 1:
                report_path = matches[0]
            elif not matches:
                err_console.print(f"[red]Report {report_id!r} not found.[/red]")
                raise typer.Exit(1)
            else:
                err_console.print(f"[red]Ambiguous ID: {len(matches)} matches.[/red]")
                raise typer.Exit(1)
    else:
        err_console.print("[red]Provide a report ID or use --latest.[/red]")
        raise typer.Exit(1)

    # Load report
    from praxis.core.sufficiency import SufficiencyReport

    report_data = json.loads(report_path.read_text(encoding="utf-8"))
    report = SufficiencyReport.model_validate(report_data)

    # Resolve profile/model
    resolved_profile = profile or get_active_profile_name()
    try:
        prof = load_profile(resolved_profile)
    except Exception:  # noqa: BLE001
        err_console.print(f"[red]Profile {resolved_profile!r} not found.[/red]")
        raise typer.Exit(1)  # noqa: B904

    effective_alias = model_alias or prof.sufficiency_gate_model_alias
    try:
        model_config = resolve_model_config(prof, None, effective_alias)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)  # noqa: B904

    transport = make_transport(model_config)

    from praxis.core.elicitation import plan_elicitations

    try:
        drafts = plan_elicitations(
            report,
            transport=transport,
            model=model_config.model,
            engagement_path=eng_path,
            max_drafts=max_drafts,
        )
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]Elicitation error: {exc}[/red]")
        raise typer.Exit(1)  # noqa: B904

    if output_json:
        console.print(
            json.dumps(
                [d.model_dump(mode="json") for d in drafts],
                indent=2,
                default=str,
            )
        )
        return

    if not drafts:
        console.print("[dim]No elicitation drafts needed.[/dim]")
        return

    # Pretty-print
    table = Table(title="Elicitation Drafts")
    table.add_column("#", width=3)
    table.add_column("Priority", width=10)
    table.add_column("Mode")
    table.add_column("Target")
    table.add_column("Channel", width=10)
    table.add_column("Needs")

    for i, d in enumerate(drafts, 1):
        priority_style = {
            "critical": "[red]CRITICAL[/red]",
            "high": "[yellow]HIGH[/yellow]",
            "medium": "MEDIUM",
            "low": "[dim]LOW[/dim]",
        }.get(d.priority, d.priority)
        needs = ", ".join(n[:40] for n in d.related_info_needs[:3])
        table.add_row(
            str(i),
            priority_style,
            d.mode.value,
            d.target_stakeholder_name,
            d.channel.value,
            needs,
        )

    console.print(table)

    # Print draft bodies
    for i, d in enumerate(drafts, 1):
        console.print(f"\n[bold]Draft {i}[/bold]")
        if d.drafted_subject:
            console.print(f"[bold]Subject:[/bold] {d.drafted_subject}")
        console.print(f"[dim]{d.drafted_body}[/dim]\n")
