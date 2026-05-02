"""CLI commands for skill management."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from praxis.config.engagement import find_engagement
from praxis.skills import SkillRegistry, create_skill, promote_skill
from praxis.skills.loader import parse_skill_md
from praxis.skills.manage import _build_skill_md

console = Console()
err_console = Console(stderr=True)

skill_app = typer.Typer(name="skill", help="Manage skills.")


def _resolve_engagement(engagement: str | None) -> Path:
    """Resolve the engagement path from the option or CWD."""
    if engagement is not None:
        p = Path(engagement)
        if not (p / ".praxis").is_dir():
            err_console.print(f"[red]Not an engagement directory: {p}[/red]")
            raise typer.Exit(1)
        return p

    found = find_engagement(Path.cwd())
    if found is None:
        err_console.print("[red]No engagement found. Use --engagement or cd to one.[/red]")
        raise typer.Exit(1)
    return found


@skill_app.command("list")
def skill_list(
    all_skills: bool = typer.Option(False, "--all", help="Include drafts and inactive skills."),
    category: str | None = typer.Option(None, "--category", "-c", help="Filter by category."),
    engagement: str | None = typer.Option(None, "--engagement", "-e", help="Engagement path."),
    json_output: bool = typer.Option(False, "--json", help="JSON output."),
) -> None:
    """List available skills."""
    eng_path: Path | None = None
    if engagement is not None:
        eng_path = _resolve_engagement(engagement)
    else:
        eng_path = find_engagement(Path.cwd())

    registry = SkillRegistry(engagement_path=eng_path)
    skills = registry.list_skills(only_active=not all_skills)

    if category is not None:
        skills = [s for s in skills if s.frontmatter.category == category]

    if json_output:
        import json

        data = [
            {
                "name": s.frontmatter.name,
                "category": s.frontmatter.category,
                "description": s.frontmatter.description,
                "status": s.frontmatter.status,
                "source": s.source,
            }
            for s in skills
        ]
        console.print_json(json.dumps(data))
        return

    if not skills:
        console.print("[dim]No skills found.[/dim]")
        return

    table = Table(title="Skills")
    table.add_column("Name", style="bold")
    table.add_column("Category")
    table.add_column("Status")
    table.add_column("Source")
    table.add_column("Description")

    for s in sorted(skills, key=lambda s: s.frontmatter.name):
        status_style = "green" if s.frontmatter.status == "published" else "yellow"
        table.add_row(
            s.frontmatter.name,
            s.frontmatter.category,
            f"[{status_style}]{s.frontmatter.status}[/{status_style}]",
            s.source,
            s.frontmatter.description,
        )
    console.print(table)


@skill_app.command("view")
def skill_view(
    name: str = typer.Argument(..., help="Skill name."),
    file: str | None = typer.Option(None, "--file", "-f", help="View a specific file."),
    engagement: str | None = typer.Option(None, "--engagement", "-e", help="Engagement path."),
) -> None:
    """View a skill's content."""
    eng_path: Path | None = None
    if engagement is not None:
        eng_path = _resolve_engagement(engagement)
    else:
        eng_path = find_engagement(Path.cwd())

    registry = SkillRegistry(engagement_path=eng_path)
    skill = registry.get(name)

    if skill is None:
        err_console.print(f"[red]Skill {name!r} not found.[/red]")
        raise typer.Exit(1)

    if file is not None:
        try:
            content = registry.get_file(name, file)
        except KeyError:
            err_console.print(f"[red]File {file!r} not found in skill {name!r}.[/red]")
            raise typer.Exit(1)  # noqa: B904
        console.print(content)
        return

    fm = skill.frontmatter
    console.print(f"[bold]{fm.name}[/bold] [{fm.category}]")
    console.print(f"Status: {fm.status} | Source: {skill.source}")
    console.print(f"Description: {fm.description}")
    if fm.when_to_use:
        console.print(f"\n[dim]When to use:[/dim]\n{fm.when_to_use}")
    console.print(f"\n{skill.body}")


@skill_app.command("promote")
def skill_promote(
    name: str = typer.Argument(..., help="Skill name to promote."),
    engagement: str | None = typer.Option(None, "--engagement", "-e", help="Engagement path."),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation."),
) -> None:
    """Promote a draft skill to published status."""
    eng_path = _resolve_engagement(engagement)
    registry = SkillRegistry(engagement_path=eng_path)
    skill = registry.get(name)

    if skill is None:
        err_console.print(f"[red]Skill {name!r} not found.[/red]")
        raise typer.Exit(1)

    if skill.frontmatter.status == "published":
        err_console.print(f"[yellow]Skill {name!r} is already published.[/yellow]")
        raise typer.Exit(1)

    if not yes:
        console.print(f"\n[bold]Skill:[/bold] {name}")
        console.print(f"[bold]Description:[/bold] {skill.frontmatter.description}")
        console.print(f"\n{skill.body[:500]}{'...' if len(skill.body) > 500 else ''}")
        if not typer.confirm("\nPromote this draft to published?"):
            raise typer.Abort()

    path = promote_skill(engagement_path=eng_path, name=name)
    console.print(f"[green]Skill {name!r} promoted to published at {path}.[/green]")


@skill_app.command("diff")
def skill_diff(
    name: str = typer.Argument(..., help="Skill name."),
    engagement: str | None = typer.Option(None, "--engagement", "-e", help="Engagement path."),
) -> None:
    """Show the difference between a draft and the published version."""
    eng_path = _resolve_engagement(engagement)

    # Load engagement-scoped version
    eng_registry = SkillRegistry(engagement_path=eng_path)
    eng_skill = eng_registry.get(name)

    if eng_skill is None or eng_skill.source != "engagement":
        err_console.print(f"[red]No engagement-scoped skill {name!r} found.[/red]")
        raise typer.Exit(1)

    # Load without engagement to get the base version
    base_registry = SkillRegistry(engagement_path=None)
    base_skill = base_registry.get(name)

    if base_skill is None:
        console.print(f"[dim]No base version of {name!r} — this is a new skill.[/dim]")
        console.print(f"\n{eng_skill.body}")
        return

    # Simple text diff
    import difflib

    base_text = _build_skill_md(base_skill.frontmatter, base_skill.body)
    eng_text = _build_skill_md(eng_skill.frontmatter, eng_skill.body)

    diff = difflib.unified_diff(
        base_text.splitlines(keepends=True),
        eng_text.splitlines(keepends=True),
        fromfile=f"{name} ({base_skill.source})",
        tofile=f"{name} (engagement)",
    )
    diff_text = "".join(diff)
    if diff_text:
        console.print(diff_text)
    else:
        console.print("[dim]No differences found.[/dim]")


@skill_app.command("install")
def skill_install(
    source: str = typer.Argument(..., help="Path to a skill directory."),
) -> None:
    """Install a skill to the user's skill library (~/.praxis/skills/)."""
    source_path = Path(source).resolve()
    if not source_path.is_dir():
        err_console.print(f"[red]Not a directory: {source_path}[/red]")
        raise typer.Exit(1)

    skill_md = source_path / "SKILL.md"
    if not skill_md.is_file():
        err_console.print(f"[red]No SKILL.md found in {source_path}[/red]")
        raise typer.Exit(1)

    text = skill_md.read_text(encoding="utf-8")
    frontmatter, _body = parse_skill_md(text)

    dest = Path.home() / ".praxis" / "skills" / frontmatter.category / frontmatter.name
    if dest.exists():
        err_console.print(
            f"[yellow]Skill {frontmatter.name!r} already installed at {dest}[/yellow]"
        )
        if not typer.confirm("Overwrite?"):
            raise typer.Abort()
        import shutil

        shutil.rmtree(dest)

    import shutil

    shutil.copytree(source_path, dest)
    console.print(f"[green]Installed skill {frontmatter.name!r} to {dest}[/green]")


@skill_app.command("new")
def skill_new(
    name: str = typer.Argument(..., help="Skill name."),
    category: str = typer.Option(..., "--category", "-c", help="Skill category."),
    engagement: str | None = typer.Option(None, "--engagement", "-e", help="Engagement path."),
) -> None:
    """Scaffold a new draft skill in the engagement."""
    eng_path = _resolve_engagement(engagement)

    path = create_skill(
        engagement_path=eng_path,
        name=name,
        category=category,
        description=f"TODO: describe {name}",
        body=f"# {name}\n\nTODO: Write the skill procedure.",
    )
    console.print(f"[green]Created draft skill {name!r} at {path}[/green]")
    console.print("Edit the SKILL.md, then run: praxis skill promote " + name)
