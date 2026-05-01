"""Praxis CLI — built with typer."""

import typer

from praxis import __version__

app = typer.Typer(
    name="praxis",
    help="Praxis — an agent-led IT business analysis framework.",
    invoke_without_command=True,
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Praxis — an agent-led IT business analysis framework."""


@app.command()
def version() -> None:
    """Print the Praxis version."""
    typer.echo(f"praxis {__version__}")
