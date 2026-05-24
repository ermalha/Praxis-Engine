"""``praxis doctor`` — first-run health check (D-066).

Runs ten read-only checks against the local install + active profile +
(optional) engagement and renders the results as a table. ``--json``
emits a structured report for scripting; ``--strict`` exits non-zero on
warnings as well as failures.

The original v0.3.x ``doctor`` behavior — a real LLM probe of the
resolved transport — moves to ``praxis doctor probe`` so the new
default health check is fast and free.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from praxis.cli.doctor_checks import CheckResult, run_all_checks
from praxis.config import load_profile, resolve_model_config
from praxis.config.engagement import find_engagement
from praxis.config.profiles import get_active_profile_name
from praxis.errors import ConfigError, TransportError
from praxis.transport import make_transport

console = Console()
err_console = Console(stderr=True)

doctor_app = typer.Typer(name="doctor", help="Run health checks against the local install.")


_STATUS_GLYPH = {
    "ok": "[green]✓[/green]",
    "warn": "[yellow]⚠[/yellow]",
    "fail": "[red]✗[/red]",
    "skip": "[dim]–[/dim]",
}


def _render_table(results: list[CheckResult]) -> None:
    table = Table(title="praxis doctor")
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Detail")
    for r in results:
        table.add_row(r.name, _STATUS_GLYPH[r.status], r.detail)
    console.print(table)


def _exit_code(results: list[CheckResult], *, strict: bool) -> int:
    """Non-zero on any ``fail``; in strict mode also on any ``warn``."""
    statuses = {r.status for r in results}
    if "fail" in statuses:
        return 1
    if strict and "warn" in statuses:
        return 1
    return 0


@doctor_app.callback(invoke_without_command=True)
def doctor(
    ctx: typer.Context,
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile to check."),
    engagement: str | None = typer.Option(
        None,
        "--engagement",
        "-e",
        help="Engagement path to include in the checks. Defaults to CWD discovery.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit non-zero on any warning, not just failures.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """Run all health checks against the local install + active profile + engagement.

    Use ``praxis doctor probe`` to additionally exercise the LLM transport
    (real network call).
    """
    # When the user invokes a subcommand (``doctor probe``), the callback
    # still runs first — return early so we don't run the checks twice.
    if ctx.invoked_subcommand is not None:
        return

    # Resolve engagement: explicit option, else find from CWD.
    eng_path: Path | None = (
        Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    )

    results = run_all_checks(profile_name=profile, engagement_path=eng_path)

    if json_output:
        typer.echo(json.dumps([r.model_dump() for r in results]))
    else:
        _render_table(results)

    code = _exit_code(results, strict=strict)
    if code:
        raise typer.Exit(code)


@doctor_app.command("probe")
def probe(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile to probe."),
) -> None:
    """Real LLM transport probe — sends a tiny request to confirm connectivity.

    Costs an LLM call. The default ``praxis doctor`` skips this; use this
    subcommand explicitly when you want to verify the provider round-trip.
    """
    resolved_profile = profile or get_active_profile_name()
    try:
        prof = load_profile(resolved_profile)
    except ConfigError as exc:
        err_console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[bold]Profile:[/bold] {prof.name}")

    try:
        model_config = resolve_model_config(prof)
    except ConfigError as exc:
        err_console.print(f"[red]No model config resolved:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[bold]Provider:[/bold] {model_config.provider}")
    console.print(f"[bold]Model:[/bold] {model_config.model}")
    console.print(f"[bold]API key env:[/bold] {model_config.api_key_env}")

    try:
        transport = make_transport(model_config)
    except TransportError as exc:
        err_console.print(f"[red]Transport error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print("\n[bold]Probing...[/bold]")
    result = transport.probe()

    if result.ok:
        console.print(f"[green]OK[/green] — {result.latency_ms:.0f}ms")
    else:
        console.print(f"[red]FAILED[/red] — {result.error}")
        raise typer.Exit(1)
