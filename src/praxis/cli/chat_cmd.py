"""CLI command: ``praxis chat`` — interactive agent REPL."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from praxis.config.engagement import find_engagement
from praxis.config.profiles import get_active_profile_name
from praxis.core.chat_runtime import ChatRuntime
from praxis.core.models import StreamEvent
from praxis.safety import warn_on_pii
from praxis.tools.models import ApprovalDecision
from praxis.tools.registry import ToolSpec

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


def chat(
    profile: str | None = typer.Option(None, "--profile", "-p"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    model_alias: str | None = typer.Option(None, "--model"),
    message: str | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Run a single non-interactive chat turn and exit. "
        "Useful for scripting / CI; the REPL is skipped entirely.",
    ),
) -> None:
    """Start an interactive chat session with the Praxis agent.

    With ``--message/-m`` the REPL is skipped: one turn is processed and
    the runtime closes. ``--model`` no longer has a short alias (was
    ``-m`` in v0.3.x) so that ``-m`` can carry the message, matching
    ``git commit -m`` / ``praxis queue commit -m`` convention.
    """
    resolved_profile = profile or get_active_profile_name()
    eng_path: Path | None = (
        Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    )
    if eng_path is None:
        err_console.print("[yellow]No engagement found. Some tools won't work.[/yellow]")
        err_console.print("[yellow]Run 'praxis init' to create one.[/yellow]")
        return

    try:
        runtime = ChatRuntime.create(
            profile_name=resolved_profile,
            engagement_path=eng_path,
            model_alias=model_alias,
            approval_callback=_cli_approval,
        )
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from None

    sid = runtime.start()

    # D-050: non-interactive single-turn mode. Skip the REPL banner + loop;
    # the caller wants one response and an exit code.
    if message is not None:
        warn_on_pii(message)
        try:
            for event in runtime.stream_turn(message):
                _render_event(event)
        finally:
            runtime.close()
        return

    console.print(f"[dim]Session: {sid[:12]}… | /help for commands[/dim]")
    eng_name = runtime.engagement.name if runtime.engagement else "none"
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
                result = runtime.handle_slash(user_input.strip())
                if result.text:
                    console.print(result.text)
                if not result.continue_session:
                    break
                continue

            # D-043: warn (don't block) on PII-looking input before sending.
            warn_on_pii(user_input)

            # Stream the response
            for event in runtime.stream_turn(user_input):
                _render_event(event)

    finally:
        runtime.close()
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
