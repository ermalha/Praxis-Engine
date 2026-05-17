"""``praxis ask`` — one-shot LLM query, optionally engagement-aware."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from praxis.config import load_profile, resolve_model_config
from praxis.engagement import build_engagement_digest
from praxis.errors import ConfigError, StorageError, TransportError
from praxis.transport import ChatRequest, Message, make_transport

console = Console()
err_console = Console(stderr=True)


_GUARD_INSTRUCTIONS = (
    "You are a business analyst working on engagement '{name}'. "
    "Use ONLY the facts above plus the user's question. "
    "If the answer depends on facts not present above, do NOT invent — "
    "name the gap, identify which stakeholder(s) could answer it, and "
    "propose creating an open question."
)


def ask(
    question: str = typer.Argument(..., help="The question to ask the LLM."),
    profile: str = typer.Option("default", "--profile", "-p", help="Profile to use."),
    engagement: str | None = typer.Option(
        None,
        "--engagement",
        "-e",
        help=(
            "Engagement path. When supplied, primes the LLM with the "
            "engagement's decisions, constraints, open questions, and "
            "stakeholders, and asks it to flag gaps rather than invent."
        ),
    ),
) -> None:
    """Send a one-shot question to the resolved LLM and print the response."""
    try:
        prof = load_profile(profile)
        model_config = resolve_model_config(prof)
    except ConfigError as exc:
        err_console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(1) from exc

    messages: list[Message] = []
    if engagement is not None:
        try:
            name, digest = build_engagement_digest(Path(engagement))
        except (ConfigError, StorageError) as exc:
            err_console.print(f"[red]Engagement error:[/red] {exc}")
            raise typer.Exit(1) from exc
        system_content = digest + "\n\n" + _GUARD_INSTRUCTIONS.format(name=name)
        messages.append(Message(role="system", content=system_content))

    messages.append(Message(role="user", content=question))

    try:
        transport = make_transport(model_config)
    except TransportError as exc:
        err_console.print(f"[red]Transport error:[/red] {exc}")
        raise typer.Exit(1) from exc

    request = ChatRequest(model=model_config.model, messages=messages)

    try:
        response = transport.chat(request)
    except TransportError as exc:
        err_console.print(f"[red]LLM error:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(response.content)
