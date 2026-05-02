"""Skill management — create, patch, edit, delete, promote."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from praxis.errors import SkillError

from .loader import parse_skill_md
from .models import SkillFrontmatter


def _validate_name(name: str) -> None:
    """Validate skill name format."""
    if not re.fullmatch(r"[a-z0-9-]+", name):
        raise SkillError(
            f"Skill name must match [a-z0-9-]+, got: {name!r}",
            name=name,
        )


def _write_atomic(path: Path, content: str) -> None:
    """Atomically write text to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    tmp.rename(path)


def _build_skill_md(frontmatter: SkillFrontmatter, body: str) -> str:
    """Build a SKILL.md file from frontmatter and body."""
    fm_dict = frontmatter.model_dump(mode="json")
    fm_yaml = yaml.safe_dump(fm_dict, default_flow_style=False, sort_keys=False)
    return f"---\n{fm_yaml}---\n\n{body}\n"


def create_skill(
    *,
    engagement_path: Path,
    name: str,
    category: str,
    description: str,
    body: str,
) -> Path:
    """Create a new draft skill in the engagement scope.

    Returns the path to the created SKILL.md.

    Raises:
        SkillError: If name is invalid or skill already exists.
    """
    _validate_name(name)

    skill_dir = engagement_path / ".praxis" / "skills" / category / name
    skill_md = skill_dir / "SKILL.md"

    if skill_md.exists():
        raise SkillError(
            f"Skill {name!r} already exists at {skill_dir}",
            name=name,
            path=str(skill_dir),
        )

    frontmatter = SkillFrontmatter(
        name=name,
        category=category,
        description=description,
        human_curated=False,
        status="draft",
    )

    content = _build_skill_md(frontmatter, body)
    _write_atomic(skill_md, content)

    return skill_md


def patch_skill(
    *,
    engagement_path: Path,
    name: str,
    description: str | None = None,
    body: str | None = None,
    patch_text: str | None = None,
) -> Path:
    """Patch an existing skill, creating a draft copy in engagement scope.

    If *body* is provided, it replaces the body entirely.
    If *patch_text* is provided, it is applied as a unified diff (not yet implemented).

    Returns the path to the patched SKILL.md.

    Raises:
        SkillError: If the skill cannot be found or patched.
    """
    _validate_name(name)

    # Find the skill in all locations
    from .loader import load_skills

    skills = load_skills(engagement_path=engagement_path)
    skill = None
    for s in skills:
        if s.frontmatter.name == name:
            skill = s
            break

    if skill is None:
        raise SkillError(f"Skill {name!r} not found", name=name)

    # Build the patched version
    fm = skill.frontmatter.model_copy()
    fm_dict = fm.model_dump(mode="json")

    if description is not None:
        fm_dict["description"] = description

    # Always flip to draft when agent patches
    fm_dict["status"] = "draft"

    new_fm = SkillFrontmatter(**fm_dict)
    new_body = body if body is not None else skill.body

    if patch_text is not None and body is None:
        # Simple line-based patch: for now just append the patch content
        # A full unified diff implementation can be added later
        new_body = f"{skill.body}\n\n{patch_text}"

    # Write to engagement scope
    skill_dir = engagement_path / ".praxis" / "skills" / new_fm.category / name
    skill_md = skill_dir / "SKILL.md"
    content = _build_skill_md(new_fm, new_body)
    _write_atomic(skill_md, content)

    return skill_md


def delete_skill(
    *,
    engagement_path: Path,
    name: str,
) -> None:
    """Delete a draft skill from engagement scope.

    Only deletes engagement-scoped skills. Bundled/user skills cannot be
    deleted via this function.

    Raises:
        SkillError: If the skill is not found in engagement scope.
    """
    _validate_name(name)

    eng_skills = engagement_path / ".praxis" / "skills"
    if not eng_skills.is_dir():
        raise SkillError(
            f"No engagement skills directory at {eng_skills}",
            name=name,
        )

    # Find the skill directory
    for category_dir in eng_skills.iterdir():
        if not category_dir.is_dir():
            continue
        skill_dir = category_dir / name
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").is_file():
            import shutil

            shutil.rmtree(skill_dir)
            return

    raise SkillError(
        f"Skill {name!r} not found in engagement scope",
        name=name,
    )


def promote_skill(
    *,
    engagement_path: Path,
    name: str,
) -> Path:
    """Promote a draft skill to published status.

    Reads the skill, flips ``status`` from ``draft`` to ``published``,
    and writes it back.

    Returns the path to the updated SKILL.md.

    Raises:
        SkillError: If the skill is not found or already published.
    """
    _validate_name(name)

    eng_skills = engagement_path / ".praxis" / "skills"

    # Find the skill in engagement scope
    skill_md: Path | None = None
    for category_dir in sorted(eng_skills.iterdir()) if eng_skills.is_dir() else []:
        if not category_dir.is_dir():
            continue
        candidate = category_dir / name / "SKILL.md"
        if candidate.is_file():
            skill_md = candidate
            break

    if skill_md is None:
        raise SkillError(
            f"Skill {name!r} not found in engagement scope",
            name=name,
        )

    text = skill_md.read_text(encoding="utf-8")
    frontmatter, body = parse_skill_md(text)

    if frontmatter.status == "published":
        raise SkillError(
            f"Skill {name!r} is already published",
            name=name,
        )

    fm_dict = frontmatter.model_dump(mode="json")
    fm_dict["status"] = "published"
    new_fm = SkillFrontmatter(**fm_dict)

    content = _build_skill_md(new_fm, body)
    _write_atomic(skill_md, content)

    return skill_md
