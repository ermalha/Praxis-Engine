"""``praxis config`` commands — inspect resolved configuration."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from praxis.config import (
    find_engagement,
    load_engagement_config,
    load_global_config,
    load_profile,
)
from praxis.config.profiles import get_active_profile_name
from praxis.errors import ConfigError

config_app = typer.Typer(name="config", help="Inspect Praxis configuration.")


@config_app.command("show")
def config_show(
    profile_name: str | None = typer.Option(  # noqa: B008
        None,
        "--profile",
        "-p",
        help="Profile name to show config for.",
    ),
    engagement_path: str | None = typer.Option(  # noqa: B008
        None,
        "--engagement",
        "-e",
        help="Engagement path.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON."),  # noqa: B008
) -> None:
    """Show the resolved effective configuration."""
    result: dict[str, object] = {}

    # Global
    try:
        global_cfg = load_global_config()
        result["global"] = global_cfg.model_dump(mode="json")
    except ConfigError as exc:
        result["global"] = {"error": str(exc)}

    # Profile
    p_name = profile_name or get_active_profile_name()
    try:
        prof = load_profile(p_name)
        result["profile"] = prof.model_dump(mode="json")
    except ConfigError:
        result["profile"] = {"name": p_name, "status": "not found"}

    # Engagement
    eng_path = Path(engagement_path) if engagement_path else find_engagement(Path.cwd())
    if eng_path is not None:
        try:
            eng_cfg = load_engagement_config(eng_path)
            data = eng_cfg.model_dump(mode="json")
            data["active"] = True
            data["path"] = str(eng_path)
            result["engagement"] = data
        except ConfigError as exc:
            result["engagement"] = {"error": str(exc)}
    else:
        result["engagement"] = {"active": False}

    if as_json:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        _print_rich(result)


def _print_rich(result: dict[str, object]) -> None:
    """Pretty-print config using Rich."""
    from rich.console import Console
    from rich.tree import Tree

    console = Console()
    tree = Tree("[bold]Praxis Configuration[/bold]")

    for section_name, section_data in result.items():
        branch = tree.add(f"[bold cyan]{section_name}[/bold cyan]")
        if section_data is None:
            branch.add("[dim]not set[/dim]")
        elif isinstance(section_data, dict):
            for key, value in section_data.items():
                branch.add(f"{key}: {value}")
        else:
            branch.add(str(section_data))

    console.print(tree)
