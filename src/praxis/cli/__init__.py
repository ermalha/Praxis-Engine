"""Praxis CLI — built with typer."""

import typer

from praxis import __version__

from .audit_cmd import audit_app
from .config_cmd import config_app
from .init_cmd import init
from .profile import profile_app

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


app.command("init")(init)
app.add_typer(profile_app)
app.add_typer(config_app)
app.add_typer(audit_app)
