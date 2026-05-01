"""``praxis init`` command — initialize an engagement."""

from __future__ import annotations

from pathlib import Path

import typer

from praxis.config import init_engagement
from praxis.errors import ConfigError


def init(
    path: Path = typer.Argument(  # noqa: B008
        ".",
        help="Directory to initialize as an engagement.",
        exists=False,
    ),
    name: str = typer.Option(  # noqa: B008
        ...,
        "--name",
        "-n",
        help="Human-readable engagement name.",
        prompt="Engagement name",
    ),
    methodology: str = typer.Option(  # noqa: B008
        "none",
        "--methodology",
        "-m",
        help="Methodology (agile, scrum, kanban, waterfall, hybrid, none).",
    ),
) -> None:
    """Initialize a new engagement directory."""
    resolved = Path(path).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    try:
        config = init_engagement(resolved, name, methodology=methodology)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Engagement '{config.name}' initialized at {resolved}")
