"""Chunk 15 integration tests — Starter Skill Library."""

from __future__ import annotations

from pathlib import Path

from praxis.skills.loader import load_bundled_skills
from praxis.skills.registry import SkillRegistry

EXPECTED_SKILLS = {
    "interview-preparation",
    "stakeholder-analysis",
    "gap-analysis",
    "process-modeling-bpmn",
    "decision-matrix-construction",
    "raci-construction",
    "invest-story-writing",
    "acceptance-criteria-gwt",
    "requirements-traceability-matrix",
    "adr-authoring",
    "status-report",
    "risk-register-entry",
}


def test_all_starter_skills_load_and_validate(tmp_engagement: Path) -> None:
    """All 12 starter skills load via SkillRegistry and meet quality bar."""
    registry = SkillRegistry(tmp_engagement)
    skills = registry.list_skills(only_active=False)
    names = {s.frontmatter.name for s in skills}

    assert EXPECTED_SKILLS.issubset(names), f"Missing: {EXPECTED_SKILLS - names}"

    for s in skills:
        if s.source == "bundled" and s.frontmatter.name in EXPECTED_SKILLS:
            assert s.frontmatter.status == "published"
            assert s.frontmatter.human_curated is True
            assert len(s.body) >= 300, (
                f"Skill {s.frontmatter.name!r} body too short: {len(s.body)} chars"
            )


def test_load_bundled_skills_convenience() -> None:
    """load_bundled_skills() returns all 12 starter skills."""
    skills = load_bundled_skills()
    names = {s.frontmatter.name for s in skills}

    assert len(skills) >= 12
    assert EXPECTED_SKILLS.issubset(names), f"Missing: {EXPECTED_SKILLS - names}"


def test_every_starter_skill_has_templates() -> None:
    """Every starter skill ships at least one template file."""
    skills = load_bundled_skills()
    for s in skills:
        if s.frontmatter.name in EXPECTED_SKILLS:
            assert len(s.templates) >= 1, f"Skill {s.frontmatter.name!r} has no templates"


def test_procedural_skills_have_examples() -> None:
    """Procedural skills (story-writing, GWT, ADR) ship examples."""
    skills = load_bundled_skills()
    procedural = {"invest-story-writing", "acceptance-criteria-gwt", "adr-authoring"}
    skills_by_name = {s.frontmatter.name: s for s in skills}

    for name in procedural:
        skill = skills_by_name[name]
        assert len(skill.examples) >= 2, (
            f"Procedural skill {name!r} needs >=2 examples, has {len(skill.examples)}"
        )


def test_skill_categories_match_directory_structure() -> None:
    """Each skill's category matches its parent directory name."""
    skills = load_bundled_skills()
    for s in skills:
        category_dir = s.path.parent.name
        assert s.frontmatter.category == category_dir, (
            f"Skill {s.frontmatter.name!r}: category={s.frontmatter.category!r} "
            f"but directory is {category_dir!r}"
        )
