"""``praxis ask`` — one-shot LLM query."""

from __future__ import annotations

import typer
from rich.console import Console

from praxis.config import load_profile, resolve_model_config
from praxis.errors import ConfigError, TransportError
from praxis.transport import ChatRequest, Message, make_transport

console = Console()
err_console = Console(stderr=True)


def ask(
    question: str = typer.Argument(..., help="The question to ask the LLM."),
    profile: str = typer.Option("default", "--profile", "-p", help="Profile to use."),
) -> None:
    """Send a one-shot question to the resolved LLM and print the response."""
    try:
        prof = load_profile(profile)
        model_config = resolve_model_config(prof)
    except ConfigError as exc:
        err_console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1) from exc

    try:
        transport = make_transport(model_config)
    except TransportError as exc:
        err_console.print(f"[red]Transport error:[/red] {exc}")
        raise typer.Exit(1) from exc

    request = ChatRequest(
        model=model_config.model,
        messages=[Message(role="user", content=question)],
    )

    try:
        response = transport.chat(request)
    except TransportError as exc:
        err_console.print(f"[red]LLM error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(response.content)
