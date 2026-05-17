"""CLI command: ``praxis check`` — run sufficiency gate from CLI."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from praxis.config.engagement import find_engagement
from praxis.config.loader import load_profile, resolve_model_config
from praxis.config.profiles import get_active_profile_name
from praxis.core.sufficiency import run_sufficiency_gate
from praxis.transport.factory import make_transport

console = Console()
err_console = Console(stderr=True)


def check(
    artifact_kind: str = typer.Argument(..., help="Artifact kind (e.g. user-story, spec)."),
    artifact_target: str = typer.Argument(..., help="Description of the artifact target."),
    profile: str | None = typer.Option(None, "--profile", "-p"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    model_alias: str | None = typer.Option(None, "--model", "-m"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON."),
    extra_context: str | None = typer.Option(None, "--context", "-c"),
) -> None:
    """Run a sufficiency gate check for an artifact."""
    # Resolve engagement
    eng_path: Path | None = (
        Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    )
    if eng_path is None:
        err_console.print("[red]No engagement found.[/red]")
        raise typer.Exit(1)

    # Resolve profile and model
    resolved_profile = profile or get_active_profile_name()
    try:
        prof = load_profile(resolved_profile)
    except Exception:  # noqa: BLE001
        err_console.print(f"[red]Profile {resolved_profile!r} not found.[/red]")
        raise typer.Exit(1)  # noqa: B904

    # Use sufficiency model alias if set and no explicit override
    effective_alias = model_alias or prof.sufficiency_gate_model_alias
    try:
        model_config = resolve_model_config(prof, None, effective_alias)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)  # noqa: B904

    transport = make_transport(model_config)

    try:
        report = run_sufficiency_gate(
            artifact_kind,
            artifact_target,
            transport=transport,
            model=model_config.model,
            engagement_path=eng_path,
            extra_context=extra_context,
        )
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]Sufficiency gate error: {exc}[/red]")
        raise typer.Exit(1)  # noqa: B904

    if output_json:
        console.print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
        return

    # Pretty-print
    _render_report(report)


def _render_report(report: object) -> None:
    """Pretty-print a SufficiencyReport."""
    from praxis.core.sufficiency import SufficiencyReport

    assert isinstance(report, SufficiencyReport)  # noqa: S101

    # Verdict colour
    colour = {
        "sufficient": "green",
        "partial": "yellow",
        "insufficient": "red",
    }.get(report.verdict.value, "white")

    console.print(f"\n[bold]Sufficiency Check[/bold]: {report.artifact_kind}")
    console.print(f"[bold]Target[/bold]: {report.artifact_target}")
    console.print(f"[bold]Verdict[/bold]: [{colour}]{report.verdict.value.upper()}[/{colour}]")
    console.print(f"[bold]Action[/bold]: {report.recommended_action}\n")

    # Info needs table
    table = Table(title="Information Needs")
    table.add_column("Status", width=8)
    table.add_column("Need")
    table.add_column("Blocker", width=8)
    table.add_column("Have")
    table.add_column("Missing")

    status_style = {
        "known": "[green]KNOWN[/green]",
        "partial": "[yellow]PARTIAL[/yellow]",
        "unknown": "[red]UNKNOWN[/red]",
    }

    for need in report.information_needs:
        table.add_row(
            status_style.get(need.status.value, need.status.value),
            need.need,
            "[red]Yes[/red]" if need.blocker else "No",
            need.have or "-",
            need.missing or "-",
        )

    console.print(table)

    if report.elicitation_targets:
        console.print(
            f"\n[bold]Elicitation targets[/bold]: {', '.join(report.elicitation_targets)}"
        )

    console.print(f"\n[dim]{report.reasoning}[/dim]\n")
