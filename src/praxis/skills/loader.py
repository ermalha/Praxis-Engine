"""Skill loader — discovers and parses skills from filesystem locations."""

from __future__ import annotations

import importlib.resources
import logging
from pathlib import Path
from typing import Literal

import yaml

from praxis.errors import SkillError

from .models import Skill, SkillFrontmatter

logger = logging.getLogger(__name__)


def parse_skill_md(text: str) -> tuple[SkillFrontmatter, str]:
    """Parse a SKILL.md file into frontmatter and body.

    Raises:
        SkillError: If the frontmatter is missing or invalid.
    """
    text = text.strip()
    if not text.startswith("---"):
        raise SkillError("SKILL.md must start with YAML frontmatter (---)")

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise SkillError("SKILL.md frontmatter must be delimited by --- on both sides")

    raw_yaml = parts[1].strip()
    body = parts[2].strip()

    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise SkillError(f"Invalid YAML in SKILL.md frontmatter: {exc}") from exc

    if not isinstance(data, dict):
        raise SkillError("SKILL.md frontmatter must be a YAML mapping")

    try:
        frontmatter = SkillFrontmatter(**data)
    except Exception as exc:
        raise SkillError(f"Invalid skill frontmatter: {exc}") from exc

    return frontmatter, body


def _list_files(directory: Path) -> list[Path]:
    """List files in a directory, returning sorted paths."""
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file())


def _load_skill_dir(
    skill_dir: Path,
    source: Literal["bundled", "user", "engagement"],
) -> Skill:
    """Load a single skill from its directory.

    Raises:
        SkillError: If SKILL.md is missing or malformed.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise SkillError(
            f"Missing SKILL.md in {skill_dir}",
            path=str(skill_dir),
        )

    text = skill_md.read_text(encoding="utf-8")
    frontmatter, body = parse_skill_md(text)

    return Skill(
        frontmatter=frontmatter,
        body=body,
        path=skill_dir,
        references=_list_files(skill_dir / "references"),
        templates=_list_files(skill_dir / "templates"),
        examples=_list_files(skill_dir / "examples"),
        source=source,
    )


def _discover_skills(
    root: Path,
    source: Literal["bundled", "user", "engagement"],
) -> dict[str, Skill]:
    """Discover all skills under *root*.

    Expected layout: ``root/<category>/<name>/SKILL.md``.
    Returns a dict keyed by skill name.
    """
    skills: dict[str, Skill] = {}
    if not root.is_dir():
        return skills

    for category_dir in sorted(root.iterdir()):
        if not category_dir.is_dir():
            continue
        for skill_dir in sorted(category_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            try:
                skill = _load_skill_dir(skill_dir, source)
                skills[skill.frontmatter.name] = skill
            except SkillError:
                logger.warning("Skipping invalid skill at %s", skill_dir, exc_info=True)

    return skills


def _bundled_skills_root() -> Path:
    """Return the path to the bundled skills directory.

    Tries ``importlib.resources`` first (works when installed from a wheel),
    falls back to the repo-root ``skills/`` directory for dev/editable installs.
    """
    try:
        ref = importlib.resources.files("praxis") / "_bundled_skills"
        pkg_path = Path(str(ref))
        if pkg_path.is_dir():
            return pkg_path
    except (TypeError, ModuleNotFoundError):
        pass

    # Dev / editable mode: skills/ lives at the repo root
    return Path(__file__).resolve().parent.parent.parent.parent / "skills"


def load_skills(
    *,
    engagement_path: Path | None = None,
    user_home: Path | None = None,
) -> list[Skill]:
    """Load skills from all three locations with precedence.

    Precedence (higher shadows lower):
    1. Bundled (``<repo>/skills/``)
    2. User (``~/.praxis/skills/``)
    3. Engagement (``<engagement>/.praxis/skills/``)

    Args:
        engagement_path: Root of the current engagement (optional).
        user_home: Override for ``~/.praxis`` (useful in tests).

    Returns:
        Merged list of skills, with higher-precedence sources shadowing.
    """
    merged: dict[str, Skill] = {}

    # 1. Bundled skills (lowest precedence)
    bundled_root = _bundled_skills_root()
    bundled = _discover_skills(bundled_root, "bundled")
    merged.update(bundled)

    # 2. User skills
    if user_home is None:
        user_home = Path.home() / ".praxis"
    user_root = user_home / "skills"
    user_skills = _discover_skills(user_root, "user")
    for name, skill in user_skills.items():
        if name in merged:
            logger.info("User skill %r shadows bundled skill", name)
        merged[name] = skill

    # 3. Engagement skills (highest precedence)
    if engagement_path is not None:
        eng_root = engagement_path / ".praxis" / "skills"
        eng_skills = _discover_skills(eng_root, "engagement")
        for name, skill in eng_skills.items():
            if name in merged:
                logger.info("Engagement skill %r shadows %s skill", name, merged[name].source)
            merged[name] = skill

    return list(merged.values())


def load_bundled_skills() -> list[Skill]:
    """Load only the bundled starter skills.

    Convenience wrapper used by acceptance tests and the ``praxis skill list``
    CLI command to verify that all shipped skills parse correctly.
    """
    root = _bundled_skills_root()
    return list(_discover_skills(root, "bundled").values())
