"""``praxis profile`` commands — manage profiles."""

from __future__ import annotations

import json

import typer

from praxis.config import create_profile, delete_profile, get_active_profile_name, list_profiles
from praxis.errors import ConfigError

profile_app = typer.Typer(name="profile", help="Manage Praxis profiles.")


@profile_app.command("create")
def profile_create(
    name: str = typer.Argument(..., help="Profile name ([a-z0-9_-]+)."),  # noqa: B008
) -> None:
    """Create a new profile."""
    try:
        profile = create_profile(name)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Profile '{profile.name}' created.")


@profile_app.command("list")
def profile_list(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON."),  # noqa: B008
) -> None:
    """List all profiles."""
    profiles = list_profiles()
    active = get_active_profile_name()
    if as_json:
        typer.echo(json.dumps({"profiles": profiles, "active": active}))
    else:
        if not profiles:
            typer.echo("No profiles found.")
            return
        for p in profiles:
            marker = " (active)" if p == active else ""
            typer.echo(f"  {p}{marker}")


@profile_app.command("use")
def profile_use(
    name: str = typer.Argument(..., help="Profile name to activate."),  # noqa: B008
) -> None:
    """Set the active profile (via PRAXIS_PROFILE env var hint)."""
    profiles = list_profiles()
    if name not in profiles:
        typer.echo(f"Error: Profile '{name}' does not exist.", err=True)
        raise typer.Exit(code=1)
    typer.echo(
        f"To activate profile '{name}', set: export PRAXIS_PROFILE={name}\n"
        f"Or update default_profile in ~/.praxis/config.yaml."
    )


@profile_app.command("delete")
def profile_delete(
    name: str = typer.Argument(..., help="Profile name to delete."),  # noqa: B008
    force: bool = typer.Option(False, "--force", help="Delete even if active."),  # noqa: B008
) -> None:
    """Delete a profile."""
    try:
        delete_profile(name, force=force)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Profile '{name}' deleted.")
