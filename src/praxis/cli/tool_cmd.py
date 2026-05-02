"""``praxis tool`` — list, describe, and invoke tools."""

from __future__ import annotations

import json

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
) -> None:
    """List registered tools."""
    specs = default_registry.list_tools(toolset=toolset)
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
