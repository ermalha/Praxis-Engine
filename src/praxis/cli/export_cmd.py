"""``praxis export`` — package engagement state for audit hand-off (D-068)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from praxis.cli.engagement._common import _resolve_engagement
from praxis.cli.errors import handle_praxis_errors
from praxis.export import BundleFormat, ExportError, export_evidence_bundle

console = Console()
err_console = Console(stderr=True)

export_app = typer.Typer(name="export", help="Export engagement state for audit hand-off.")


def _default_output_for(format_: BundleFormat, engagement_path: Path) -> Path:
    """Choose a sensible default output path when ``--output`` is omitted."""
    stem = engagement_path.resolve().name + "-evidence"
    if format_ is BundleFormat.ZIP:
        return Path(f"./{stem}.zip")
    if format_ is BundleFormat.TAR_GZ:
        return Path(f"./{stem}.tar.gz")
    return Path(f"./{stem}")  # dir


@export_app.command("evidence")
@handle_praxis_errors
def evidence(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    bundle_format: str = typer.Option(
        "zip",
        "--format",
        "-f",
        help="Bundle format: zip (default), tar.gz, or dir.",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path. Defaults to <engagement-name>-evidence.<ext> in CWD.",
    ),
) -> None:
    """Bundle the engagement's ``.praxis/`` tree + a content-hashed MANIFEST.json.

    The resulting archive is an audit-ready snapshot: the recipient can
    re-hash each file and compare against MANIFEST.json to verify
    integrity. Same engagement state in → same hashes out (deterministic).
    """
    eng_path = _resolve_engagement(engagement)

    try:
        fmt = BundleFormat(bundle_format)
    except ValueError as exc:
        valid = ", ".join(m.value for m in BundleFormat)
        err_console.print(f"[red]Unknown --format {bundle_format!r}. Valid formats: {valid}.[/red]")
        raise typer.Exit(1) from exc

    output_path = Path(output) if output else _default_output_for(fmt, eng_path)

    try:
        written = export_evidence_bundle(eng_path, output_path, bundle_format=fmt)
    except ExportError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    console.print(f"[green]Wrote evidence bundle ({fmt.value}):[/green] {written}")
