"""CLI commands: ``praxis browser`` — manage browser harness."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

browser_app = typer.Typer(name="browser", help="Manage browser harness integration.")


@browser_app.command("install")
def browser_install(
    path: str | None = typer.Option(None, "--path", "-p", help="Custom install path."),
) -> None:
    """Clone browser-harness and symlink skills."""
    from praxis.integrations.browser.install import install

    console = Console()
    install_path = Path(path) if path else None
    dest = install(install_path)
    console.print(f"[green]Browser harness installed at {dest}[/green]")


@browser_app.command("doctor")
def browser_doctor(
    path: str | None = typer.Option(None, "--path", "-p", help="Custom install path."),
) -> None:
    """Verify browser-harness installation."""
    from praxis.integrations.browser.install import doctor

    console = Console()
    install_path = Path(path) if path else None
    results = doctor(install_path)
    if results.get("installed"):
        console.print(f"[green]{results['message']}[/green]")
    else:
        console.print(f"[yellow]{results['message']}[/yellow]")
