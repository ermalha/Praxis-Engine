"""``praxis doctor`` — diagnose config and connectivity."""

from __future__ import annotations

import typer
from rich.console import Console

from praxis.config import load_profile, resolve_model_config
from praxis.config.profiles import get_active_profile_name
from praxis.errors import ConfigError, TransportError
from praxis.transport import make_transport

console = Console(stderr=True)

doctor_app = typer.Typer(name="doctor", help="Diagnose configuration and connectivity.")


@doctor_app.callback(invoke_without_command=True)
def doctor(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile to check."),
) -> None:
    """Check profile model config and probe the resolved transport."""
    resolved_profile = profile or get_active_profile_name()
    try:
        prof = load_profile(resolved_profile)
    except ConfigError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[bold]Profile:[/bold] {prof.name}")

    try:
        model_config = resolve_model_config(prof)
    except ConfigError as exc:
        console.print(f"[red]No model config resolved:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[bold]Provider:[/bold] {model_config.provider}")
    console.print(f"[bold]Model:[/bold] {model_config.model}")
    console.print(f"[bold]API key env:[/bold] {model_config.api_key_env}")

    try:
        transport = make_transport(model_config)
    except TransportError as exc:
        console.print(f"[red]Transport error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print("\n[bold]Probing...[/bold]")
    result = transport.probe()

    if result.ok:
        console.print(f"[green]OK[/green] — {result.latency_ms:.0f}ms")
    else:
        console.print(f"[red]FAILED[/red] — {result.error}")
        raise typer.Exit(1)
