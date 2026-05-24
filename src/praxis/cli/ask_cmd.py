"""``praxis ask`` — one-shot LLM query, optionally engagement-aware."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from praxis.config import load_profile, resolve_model_config
from praxis.config.profiles import get_active_profile_name
from praxis.engagement import build_engagement_digest
from praxis.errors import ConfigError, StorageError, TransportError
from praxis.safety import PIIBlockedError, apply_pii_policy
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
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile to use."),
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
    # D-065: PII guard now supports block/redact in addition to warn/off.
    # ``apply_pii_policy`` may return a redacted question; it may also
    # raise ``PIIBlockedError`` under PRAXIS_PII_GUARD=block.
    try:
        question, _ = apply_pii_policy(question)
    except PIIBlockedError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc

    resolved_profile = profile or get_active_profile_name()
    try:
        prof = load_profile(resolved_profile)
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
