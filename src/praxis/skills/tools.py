"""Skill tools — registered into the chunk-5 tool registry."""

from __future__ import annotations

from typing import Literal

from praxis.tools import ToolContext, ToolResult, tool

from .manage import create_skill, delete_skill, patch_skill
from .registry import SkillRegistry


def _make_registry(ctx: ToolContext) -> SkillRegistry:
    """Build a SkillRegistry from the tool context."""
    return SkillRegistry(
        engagement_path=ctx.engagement_path,
    )


@tool(
    name="skill_list",
    description="List available skills (level 0). Returns name, category, and description.",
    toolset="skills",
)
def skill_list(ctx: ToolContext, category: str | None = None) -> ToolResult:
    """Return name, category, description for active skills."""
    registry = _make_registry(ctx)
    skills = registry.list_skills(only_active=True)

    if category is not None:
        skills = [s for s in skills if s.frontmatter.category == category]

    if not skills:
        return ToolResult(content="No active skills found.", data={"skills": []})

    lines: list[str] = []
    skill_data: list[dict[str, str]] = []
    for s in sorted(skills, key=lambda s: s.frontmatter.name):
        fm = s.frontmatter
        lines.append(f"- **{fm.name}** [{fm.category}]: {fm.description}")
        skill_data.append(
            {
                "name": s.frontmatter.name,
                "category": s.frontmatter.category,
                "description": s.frontmatter.description,
            }
        )

    return ToolResult(
        content="\n".join(lines),
        data={"skills": skill_data},
    )


@tool(
    name="skill_view",
    description="Read a skill's full content (level 1) or a specific file (level 2).",
    toolset="skills",
)
def skill_view(ctx: ToolContext, name: str, file: str | None = None) -> ToolResult:
    """If file is None, return SKILL.md body. Otherwise return the named file."""
    registry = _make_registry(ctx)
    skill = registry.get(name)

    if skill is None:
        return ToolResult(content=f"Skill {name!r} not found.", data={"error": "not_found"})

    ctx.audit("skill.viewed", subject_id=name, file=file)

    if file is not None:
        try:
            content = registry.get_file(name, file)
        except KeyError:
            return ToolResult(
                content=f"File {file!r} not found in skill {name!r}.",
                data={"error": "file_not_found"},
            )
        return ToolResult(content=content, data={"skill": name, "file": file})

    # Return full SKILL.md body
    fm = skill.frontmatter
    header = (
        f"# {fm.name}\n"
        f"**Category:** {fm.category}\n"
        f"**Description:** {fm.description}\n"
        f"**Status:** {fm.status}\n\n"
    )

    file_list: list[str] = []
    for label, paths in [
        ("references", skill.references),
        ("templates", skill.templates),
        ("examples", skill.examples),
    ]:
        for p in paths:
            file_list.append(f"{label}/{p.name}")

    data: dict[str, object] = {
        "skill": name,
        "category": fm.category,
        "status": fm.status,
        "files": file_list,
    }

    content = header + skill.body
    if file_list:
        content += "\n\n**Available files:** " + ", ".join(file_list)

    return ToolResult(content=content, data=data)


@tool(
    name="skill_manage",
    description="Create, patch, or delete a skill. All writes go to engagement scope as drafts.",
    toolset="skills",
    dangerous=True,
)
def skill_manage(
    ctx: ToolContext,
    action: Literal["create", "patch", "delete"],
    name: str,
    category: str | None = None,
    description: str | None = None,
    body: str | None = None,
    patch_text: str | None = None,
) -> ToolResult:
    """Manage skills — create, patch, or delete.

    All writes go to ``<engagement>/.praxis/skills/`` with ``status=draft``.
    Promotion to published is human-only via ``praxis skill promote``.
    """
    if ctx.engagement_path is None:
        return ToolResult(
            content="No engagement active. Cannot manage skills without an engagement.",
            data={"error": "no_engagement"},
        )

    if action == "create":
        if category is None:
            return ToolResult(
                content="Category is required for creating a skill.",
                data={"error": "missing_category"},
            )
        if description is None:
            return ToolResult(
                content="Description is required for creating a skill.",
                data={"error": "missing_description"},
            )
        if body is None:
            return ToolResult(
                content="Body is required for creating a skill.",
                data={"error": "missing_body"},
            )

        path = create_skill(
            engagement_path=ctx.engagement_path,
            name=name,
            category=category,
            description=description,
            body=body,
        )
        ctx.audit("skill.created", subject_id=name, path=str(path))
        return ToolResult(
            content=f"Draft skill {name!r} created at {path}.",
            data={"skill": name, "path": str(path), "status": "draft"},
        )

    if action == "patch":
        path = patch_skill(
            engagement_path=ctx.engagement_path,
            name=name,
            description=description,
            body=body,
            patch_text=patch_text,
        )
        ctx.audit("skill.patched", subject_id=name, path=str(path))
        return ToolResult(
            content=f"Skill {name!r} patched (draft) at {path}.",
            data={"skill": name, "path": str(path), "status": "draft"},
        )

    if action == "delete":
        delete_skill(engagement_path=ctx.engagement_path, name=name)
        ctx.audit("skill.deleted", subject_id=name)
        return ToolResult(
            content=f"Skill {name!r} deleted from engagement scope.",
            data={"skill": name},
        )

    return ToolResult(
        content=f"Unknown action: {action!r}. Use create, patch, or delete.",
        data={"error": "unknown_action"},
    )
