"""``praxis tool`` — list, describe, and invoke tools."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from praxis.tools import default_registry

console = Console()
err_console = Console(stderr=True)

tool_app = typer.Typer(name="tool", help="Manage and invoke tools.")


@tool_app.command("list")
def tool_list(
    toolset: str | None = typer.Option(None, "--toolset", "-t", help="Filter by toolset."),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """List registered tools."""
    specs = default_registry.list_tools(toolset=toolset)
    if output_json:
        console.print(
            json.dumps(
                [
                    {
                        "name": spec.name,
                        "toolset": spec.toolset,
                        "dangerous": spec.dangerous,
                        "interactive": spec.interactive,
                        "description": spec.description,
                        "parameters_schema": spec.parameters_schema,
                    }
                    for spec in specs
                ],
                indent=2,
                default=str,
            )
        )
        return
    if not specs:
        console.print("[dim]No tools registered.[/dim]")
        return

    table = Table(title="Registered Tools")
    table.add_column("Name", style="bold")
    table.add_column("Toolset")
    table.add_column("Dangerous")
    table.add_column("Interactive")
    table.add_column("Description")

    for spec in specs:
        table.add_row(
            spec.name,
            spec.toolset,
            "yes" if spec.dangerous else "",
            "yes" if spec.interactive else "",
            spec.description,
        )
    console.print(table)


@tool_app.command("describe")
def tool_describe(
    name: str = typer.Argument(..., help="Tool name."),
) -> None:
    """Print the JSON Schema for a tool."""
    spec = default_registry.get(name)
    if spec is None:
        err_console.print(f"[red]Unknown tool:[/red] {name}")
        raise typer.Exit(1)

    console.print(f"[bold]{spec.name}[/bold] — {spec.description}")
    console.print(f"Toolset: {spec.toolset} | Dangerous: {spec.dangerous}")
    console.print("\n[bold]Parameters JSON Schema:[/bold]")
    console.print_json(json.dumps(spec.parameters_schema, indent=2))


@tool_app.command("invoke")
def tool_invoke(
    name: str = typer.Argument(..., help="Tool name."),
    args_json: str = typer.Option("{}", "--args-json", help="JSON object of tool arguments."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip dangerous-tool confirmation."),
) -> None:
    """Invoke a tool directly from the CLI."""
    from praxis.config.engagement import find_engagement
    from praxis.config.loader import load_engagement_config, load_profile
    from praxis.config.profiles import get_active_profile_name
    from praxis.tools.context import ToolContext

    spec = default_registry.get(name)
    if spec is None:
        err_console.print(f"[red]Unknown tool:[/red] {name}")
        raise typer.Exit(1)

    if spec.dangerous and not yes:
        err_console.print(f"[yellow]Tool {name!r} is marked dangerous.[/yellow]")
        if not typer.confirm("Proceed?"):
            raise typer.Abort()

    try:
        args = json.loads(args_json)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON:[/red] {exc}")
        raise typer.Exit(1) from None

    # Build a minimal ToolContext
    profile_name = get_active_profile_name()
    try:
        profile = load_profile(profile_name)
    except Exception:  # noqa: BLE001
        from praxis.config.models import ProfileConfig

        profile = ProfileConfig(name=profile_name)

    eng_path = Path(engagement) if engagement else find_engagement(Path.cwd())
    eng_config = None
    if eng_path is not None:
        with contextlib.suppress(Exception):
            eng_config = load_engagement_config(eng_path)

    from praxis.audit import emit

    ctx = ToolContext(
        profile=profile,
        engagement=eng_config,
        engagement_path=eng_path,
        audit=emit,
    )

    try:
        result = spec.func(ctx, **args)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"[red]Tool error:[/red] {exc}")
        raise typer.Exit(1) from None

    console.print_json(json.dumps(result, indent=2, default=str))
