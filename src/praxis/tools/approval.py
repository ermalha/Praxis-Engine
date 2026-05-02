"""Approval gate for dangerous tools."""

from __future__ import annotations

import json

from rich.console import Console
from rich.prompt import Prompt

from praxis.tools.models import ApprovalDecision
from praxis.tools.registry import ToolSpec

console = Console(stderr=True)


def cli_approval_callback(spec: ToolSpec, args: dict[str, object]) -> ApprovalDecision:
    """Prompt the user via CLI for tool approval.

    Shows the tool name, description, and arguments, then asks for
    [a]pprove / [r]eject / [m]odify.
    """
    console.print(f"\n[bold yellow]Dangerous tool:[/bold yellow] {spec.name}")
    console.print(f"[dim]{spec.description}[/dim]")
    console.print("[bold]Arguments:[/bold]")
    console.print_json(json.dumps(args, indent=2, default=str))

    choice = Prompt.ask(
        "[a]pprove / [r]eject / [m]odify",
        choices=["a", "r", "m"],
        default="r",
    )

    if choice == "a":
        return ApprovalDecision.APPROVE
    if choice == "m":
        return ApprovalDecision.MODIFY
    return ApprovalDecision.REJECT
