"""Praxis CLI — built with typer."""

import typer

from praxis import __version__

from .ask_cmd import ask
from .audit_cmd import audit_app
from .chat_cmd import chat
from .config_cmd import config_app
from .doctor_cmd import doctor_app
from .engagement_cmd import engagement_app
from .init_cmd import init
from .profile import profile_app
from .session_cmd import session_app
from .skill_cmd import skill_app
from .tool_cmd import tool_app

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
app.command("ask")(ask)
app.command("chat")(chat)
app.add_typer(profile_app)
app.add_typer(config_app)
app.add_typer(audit_app)
app.add_typer(doctor_app)
app.add_typer(engagement_app)
app.add_typer(session_app)
app.add_typer(skill_app)
app.add_typer(tool_app)
