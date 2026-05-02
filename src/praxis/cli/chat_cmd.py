"""CLI command: ``praxis chat`` — interactive agent REPL."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from praxis.config.engagement import find_engagement
from praxis.config.loader import (
    load_engagement_config,
    load_profile,
    resolve_model_config,
)
from praxis.core.agent import Agent
from praxis.core.models import StreamEvent
from praxis.skills import SkillRegistry
from praxis.tools.models import ApprovalDecision
from praxis.tools.registry import ToolSpec, default_registry
from praxis.transport.factory import make_transport

console = Console()
err_console = Console(stderr=True)


def _cli_approval(spec: ToolSpec, args: dict[str, object]) -> ApprovalDecision:
    """Prompt for dangerous-tool approval."""
    console.print(f"\n[yellow]Tool: {spec.name}[/yellow] (dangerous)")
    console.print(f"  {spec.description}")
    for k, v in args.items():
        console.print(f"  {k}: {v}")
    choice = typer.prompt("[a]pprove / [r]eject", default="a")
    if choice.lower().startswith("r"):
        return ApprovalDecision.REJECT
    return ApprovalDecision.APPROVE


def _handle_slash(
    cmd: str,
    agent: Agent,
    db_path: Path,
) -> bool:
    """Handle slash commands. Returns True to continue, False to exit."""
    parts = cmd.strip().split(None, 1)
    command = parts[0].lower()

    if command == "/exit":
        return False

    if command == "/new":
        agent.end_session()
        sid = agent.start_session()
        console.print(f"[dim]New session: {sid}[/dim]")
        return True

    if command == "/sessions":
        from praxis.core.session import list_sessions

        sessions = list_sessions(db_path)
        for s in sessions:
            status = "ended" if s.ended_at else "active"
            summary = f" — {s.summary}" if s.summary else ""
            console.print(f"  [{status}] {s.id[:12]}…{summary}")
        return True

    if command == "/skills":
        tools = default_registry.list_tools(toolset="skills")
        if not tools:
            console.print("[dim]No skill tools.[/dim]")
        for t in tools:
            console.print(f"  - {t.name}: {t.description}")
        return True

    if command == "/tools":
        for t in default_registry.list_tools():
            tag = " [dangerous]" if t.dangerous else ""
            console.print(f"  - {t.name} ({t.toolset}){tag}")
        return True

    if command == "/help":
        console.print(
            "/exit  — end session and quit\n"
            "/new   — start a new session\n"
            "/sessions — list recent sessions\n"
            "/skills — list active skills\n"
            "/tools  — list available tools\n"
            "/help   — show this help"
        )
        return True

    console.print(f"[red]Unknown command: {command}[/red]")
    return True


def chat(
    profile: str = typer.Option("default", "--profile", "-p"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    model_alias: str | None = typer.Option(None, "--model", "-m"),
) -> None:
    """Start an interactive chat session with the Praxis agent."""
    # Resolve engagement
    eng_path: Path | None = (
        Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    )
    eng_config = None

    if eng_path is not None:
        eng_config = load_engagement_config(eng_path)

    # Resolve profile and model
    try:
        prof = load_profile(profile)
    except Exception:  # noqa: BLE001
        err_console.print(f"[red]Profile {profile!r} not found.[/red]")
        raise typer.Exit(1)  # noqa: B904

    try:
        model_config = resolve_model_config(prof, eng_config, model_alias)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)  # noqa: B904

    transport = make_transport(model_config)
    skill_registry = SkillRegistry(engagement_path=eng_path)

    agent = Agent(
        profile=prof,
        engagement=eng_config,
        engagement_path=eng_path,
        transport=transport,
        tool_registry=default_registry,
        skill_registry=skill_registry,
        approval_callback=_cli_approval,
        model=model_config.model,
    )

    if eng_path is None:
        err_console.print("[yellow]No engagement found. Some tools won't work.[/yellow]")
        err_console.print("[yellow]Run 'praxis init' to create one.[/yellow]")
        return

    db_path = eng_path / ".praxis" / "state" / "praxis.db"
    sid = agent.start_session()
    console.print(f"[dim]Session: {sid[:12]}… | /help for commands[/dim]")
    eng_name = eng_config.name if eng_config else "none"
    console.print(f"[dim]Engagement: {eng_name}[/dim]\n")

    try:
        while True:
            try:
                user_input = console.input("[bold]> [/bold]")
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input.strip():
                continue

            if user_input.strip().startswith("/"):
                if not _handle_slash(user_input.strip(), agent, db_path):
                    break
                continue

            # Stream the response
            for event in agent.stream_turn(user_input):
                _render_event(event)

    finally:
        agent.end_session()
        console.print("\n[dim]Session ended.[/dim]")


def _render_event(event: StreamEvent) -> None:
    """Render a stream event to the console."""
    if event.type == "text_delta" and event.text:
        console.print(event.text, end="")
    elif event.type == "tool_call_start":
        console.print(f"\n[dim]⚙ {event.tool_name}[/dim]", end="")
    elif event.type == "tool_result":
        if event.is_error:
            console.print(" [red]✗[/red]")
        else:
            console.print(" [green]✓[/green]")
    elif event.type == "done":
        console.print()  # Final newline
