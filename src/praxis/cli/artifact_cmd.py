"""``praxis artifact`` commands — generate and inspect state-grounded artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from praxis.artifacts import generate_artifact, list_artifacts
from praxis.config.engagement import find_engagement
from praxis.config.loader import load_profile, resolve_model_config
from praxis.config.profiles import get_active_profile_name
from praxis.transport import make_transport

artifact_app = typer.Typer(name="artifact", help="Generate and inspect artifacts.")
console = Console()
err_console = Console(stderr=True)

_PROMPTS = {
    "scope-brief": (
        "Create an MVP scope brief using only known engagement facts. Include in-scope, "
        "out-of-scope, success metrics, constraints, risks, and open questions."
    ),
    "backlog": (
        "Generate a backlog artifact for the implementation team. Include epics, user "
        "stories, acceptance criteria, dependencies, open questions, and risks. Mark "
        "uncertain items clearly."
    ),
    "traceability": (
        "Create a traceability matrix from business outcomes to MVP epics and candidate "
        "stories. Make gaps visible."
    ),
}
_OUTPUT_DIRS = {
    "scope-brief": "reports",
    "backlog": "stories",
    "traceability": "matrices",
}


def _resolve_engagement(engagement: str | None) -> Path:
    eng = Path(engagement) if engagement is not None else find_engagement(Path.cwd())
    if eng is None:
        err_console.print("[red]No engagement found.[/red]")
        raise typer.Exit(1)
    return eng


@artifact_app.command("generate")
def artifact_generate(
    kind: str = typer.Argument(..., help="scope-brief, backlog, traceability, or custom kind."),
    prompt: str | None = typer.Option(None, "--prompt", help="Custom artifact prompt."),
    profile: str | None = typer.Option(None, "--profile", "-p"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    model_alias: str | None = typer.Option(None, "--model", "-m"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    """Generate an artifact from persisted engagement state and print its path."""
    eng = _resolve_engagement(engagement)
    resolved_profile = profile or get_active_profile_name()
    prof = load_profile(resolved_profile)
    model_config = resolve_model_config(prof, None, model_alias)
    transport = make_transport(model_config)
    result = generate_artifact(
        engagement_path=eng,
        profile=prof,
        model=model_config.model,
        transport=transport,
        artifact_kind=kind,
        prompt=prompt or _PROMPTS.get(kind, f"Generate a {kind} artifact."),
        output_dir=_OUTPUT_DIRS.get(kind, "reports"),
    )
    if output_json:
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, default=str))
        return
    console.print(result.content)
    console.print(f"\n[green]Created artifact:[/green] {result.path}")
    if result.sufficiency_verdict:
        console.print(
            f"[dim]Bound sufficiency report: {result.sufficiency_report_path} "
            f"(verdict: {result.sufficiency_verdict})[/dim]"
        )


@artifact_app.command("list")
def artifact_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    output_json: bool = typer.Option(False, "--json"),
    profile: str | None = typer.Option(  # noqa: ARG001
        None,
        "--profile",
        "-p",
        help=(
            "Accepted for CLI consistency with `artifact generate`; "
            "unused (listing is a filesystem read)."
        ),
    ),
) -> None:
    """List generated artifacts."""
    eng = _resolve_engagement(engagement)
    artifacts = list_artifacts(eng)
    if output_json:
        typer.echo(
            json.dumps(
                [a.model_dump(mode="json") for a in artifacts],
                indent=2,
                default=str,
            )
        )
        return
    if not artifacts:
        console.print("[dim]No artifacts.[/dim]")
        return
    for artifact in artifacts:
        console.print(f"- [{artifact.artifact_kind}] {artifact.path}")


@artifact_app.command("show")
def artifact_show(path: str = typer.Argument(..., help="Artifact file path.")) -> None:
    """Print an artifact file."""
    artifact_path = Path(path).expanduser().resolve()
    if not artifact_path.is_file():
        err_console.print(f"[red]Artifact not found:[/red] {artifact_path}")
        raise typer.Exit(1)
    console.print(artifact_path.read_text(encoding="utf-8", errors="replace"))
    console.print(f"\n[dim]Path: {artifact_path}[/dim]")
