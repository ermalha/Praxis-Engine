"""Tests for skill subsystem — models, loader, registry, tools, manage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from praxis.config.models import ProfileConfig
from praxis.errors import SkillError
from praxis.skills import (
    SkillFrontmatter,
    SkillRegistry,
    create_skill,
    delete_skill,
    load_skills,
    parse_skill_md,
    patch_skill,
    promote_skill,
)
from praxis.skills.tools import skill_list, skill_manage, skill_view
from praxis.tools import ToolContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_SKILL_MD = """\
---
name: test-skill
category: testing
description: A test skill.
when_to_use: When testing.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# Test Skill

This is the body.
"""

DRAFT_SKILL_MD = """\
---
name: draft-skill
category: testing
description: A draft skill.
human_curated: false
status: draft
schema_version: 1
---

# Draft Skill

Draft body.
"""


def _write_skill(root: Path, category: str, name: str, content: str) -> Path:
    """Write a SKILL.md to the expected directory structure."""
    skill_dir = root / category / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(content)
    return skill_dir


def _make_context(
    engagement_path: Path | None = None,
) -> ToolContext:
    return ToolContext(
        profile=ProfileConfig(name="test"),
        audit=MagicMock(),
        engagement_path=engagement_path,
    )


# ---------------------------------------------------------------------------
# Frontmatter validation
# ---------------------------------------------------------------------------


class TestFrontmatter:
    def test_valid_frontmatter(self) -> None:
        fm = SkillFrontmatter(
            name="my-skill",
            category="requirements",
            description="A skill",
        )
        assert fm.name == "my-skill"
        assert fm.status == "published"
        assert fm.schema_version == 1

    def test_invalid_name_uppercase(self) -> None:
        with pytest.raises(ValueError, match="must match"):
            SkillFrontmatter(name="MySkill", category="test", description="x")

    def test_invalid_name_spaces(self) -> None:
        with pytest.raises(ValueError, match="must match"):
            SkillFrontmatter(name="my skill", category="test", description="x")

    def test_invalid_category(self) -> None:
        with pytest.raises(ValueError, match="must match"):
            SkillFrontmatter(name="ok", category="Bad Category!", description="x")

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):
            SkillFrontmatter(name="ok", category="test", description="x", unknown="bad")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class TestParsing:
    def test_parse_valid(self) -> None:
        fm, body = parse_skill_md(VALID_SKILL_MD)
        assert fm.name == "test-skill"
        assert fm.category == "testing"
        assert "Test Skill" in body

    def test_parse_missing_frontmatter(self) -> None:
        with pytest.raises(SkillError, match="must start with"):
            parse_skill_md("No frontmatter here")

    def test_parse_invalid_yaml(self) -> None:
        with pytest.raises(SkillError, match="Invalid YAML"):
            parse_skill_md("---\n[invalid: yaml:\n---\nbody")

    def test_parse_non_mapping(self) -> None:
        with pytest.raises(SkillError, match="must be a YAML mapping"):
            parse_skill_md("---\n- a list\n---\nbody")

    def test_parse_invalid_fields(self) -> None:
        bad = "---\nname: BAD NAME\ncategory: test\ndescription: x\nschema_version: 1\n---\nbody"
        with pytest.raises(SkillError, match="Invalid skill frontmatter"):
            parse_skill_md(bad)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class TestLoader:
    def test_load_from_single_location(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)

        from praxis.skills.loader import _discover_skills

        skills = _discover_skills(bundled, "bundled")
        assert "test-skill" in skills
        assert skills["test-skill"].source == "bundled"

    def test_precedence_user_shadows_bundled(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        user_home = tmp_path / "user_home"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)

        user_version = VALID_SKILL_MD.replace("A test skill.", "User override.")
        _write_skill(user_home / "skills", "testing", "test-skill", user_version)

        # Monkey-patch the bundled root
        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root

        def patched() -> Path:
            return bundled

        loader_mod._bundled_skills_root = patched
        try:
            skills = load_skills(user_home=user_home)
            skill = [s for s in skills if s.frontmatter.name == "test-skill"][0]
            assert skill.source == "user"
            assert "User override" in skill.frontmatter.description
        finally:
            loader_mod._bundled_skills_root = orig

    def test_precedence_engagement_shadows_all(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        user_home = tmp_path / "user_home"
        engagement = tmp_path / "engagement"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)

        eng_version = VALID_SKILL_MD.replace("A test skill.", "Engagement override.")
        _write_skill(engagement / ".praxis" / "skills", "testing", "test-skill", eng_version)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            skills = load_skills(
                engagement_path=engagement,
                user_home=user_home,
            )
            skill = [s for s in skills if s.frontmatter.name == "test-skill"][0]
            assert skill.source == "engagement"
            assert "Engagement override" in skill.frontmatter.description
        finally:
            loader_mod._bundled_skills_root = orig

    def test_references_templates_examples(self, tmp_path: Path) -> None:
        skill_dir = _write_skill(tmp_path / "skills", "testing", "test-skill", VALID_SKILL_MD)
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "guide.md").write_text("# Guide")
        (skill_dir / "templates").mkdir()
        (skill_dir / "templates" / "output.md").write_text("# Template")
        (skill_dir / "examples").mkdir()
        (skill_dir / "examples" / "example1.md").write_text("# Example")

        from praxis.skills.loader import _discover_skills

        skills = _discover_skills(tmp_path / "skills", "bundled")
        skill = skills["test-skill"]
        assert len(skill.references) == 1
        assert len(skill.templates) == 1
        assert len(skill.examples) == 1


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def _make_registry(self, tmp_path: Path) -> SkillRegistry:
        """Create a registry with a patched bundled root."""
        bundled = tmp_path / "bundled"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)
        _write_skill(bundled, "testing", "draft-skill", DRAFT_SKILL_MD)

        import praxis.skills.loader as loader_mod

        self._orig_bundled = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled

        return SkillRegistry(user_home=tmp_path / "empty_home")

    def _cleanup(self) -> None:
        import praxis.skills.loader as loader_mod

        loader_mod._bundled_skills_root = self._orig_bundled

    def test_list_active_excludes_drafts(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        try:
            active = reg.list_skills(only_active=True)
            names = [s.frontmatter.name for s in active]
            assert "test-skill" in names
            assert "draft-skill" not in names
        finally:
            self._cleanup()

    def test_list_all_includes_drafts(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        try:
            all_skills = reg.list_skills(only_active=False)
            names = [s.frontmatter.name for s in all_skills]
            assert "test-skill" in names
            assert "draft-skill" in names
        finally:
            self._cleanup()

    def test_get_by_name(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        try:
            skill = reg.get("test-skill")
            assert skill is not None
            assert skill.frontmatter.name == "test-skill"
        finally:
            self._cleanup()

    def test_get_unknown(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        try:
            assert reg.get("nonexistent") is None
        finally:
            self._cleanup()

    def test_get_file(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        skill_dir = _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "guide.md").write_text("# Guide content")

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            reg = SkillRegistry(user_home=tmp_path / "empty_home")
            content = reg.get_file("test-skill", "guide.md")
            assert "Guide content" in content
        finally:
            loader_mod._bundled_skills_root = orig

    def test_get_file_not_found(self, tmp_path: Path) -> None:
        reg = self._make_registry(tmp_path)
        try:
            with pytest.raises(KeyError, match="not found"):
                reg.get_file("test-skill", "nonexistent.md")
        finally:
            self._cleanup()

    def test_requires_toolsets_filtering(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        requires_md = VALID_SKILL_MD.replace(
            "requires_toolsets: []",
            "requires_toolsets:\n  - jira",
        )
        skill_md = requires_md.replace("test-skill", "requires-jira")
        _write_skill(bundled, "testing", "requires-jira", skill_md)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            # Without jira enabled
            reg = SkillRegistry(
                user_home=tmp_path / "empty_home",
                enabled_toolsets=set(),
            )
            active = reg.list_skills(only_active=True)
            assert not any(s.frontmatter.name == "requires-jira" for s in active)

            # With jira enabled
            reg2 = SkillRegistry(
                user_home=tmp_path / "empty_home",
                enabled_toolsets={"jira"},
            )
            active2 = reg2.list_skills(only_active=True)
            assert any(s.frontmatter.name == "requires-jira" for s in active2)
        finally:
            loader_mod._bundled_skills_root = orig

    def test_fallback_for_toolsets_filtering(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        fallback_md = VALID_SKILL_MD.replace(
            "fallback_for_toolsets: []",
            "fallback_for_toolsets:\n  - jira",
        )
        skill_md = fallback_md.replace("test-skill", "fallback-jira")
        _write_skill(bundled, "testing", "fallback-jira", skill_md)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            # Without jira — fallback is active
            reg = SkillRegistry(
                user_home=tmp_path / "empty_home",
                enabled_toolsets=set(),
            )
            active = reg.list_skills(only_active=True)
            assert any(s.frontmatter.name == "fallback-jira" for s in active)

            # With jira — fallback becomes inactive
            reg2 = SkillRegistry(
                user_home=tmp_path / "empty_home",
                enabled_toolsets={"jira"},
            )
            active2 = reg2.list_skills(only_active=True)
            assert not any(s.frontmatter.name == "fallback-jira" for s in active2)
        finally:
            loader_mod._bundled_skills_root = orig

    def test_required_engagement_fields_filtering(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        fields_md = VALID_SKILL_MD.replace(
            "required_engagement_fields: []",
            "required_engagement_fields:\n  - glossary",
        )
        skill_md = fields_md.replace("test-skill", "needs-glossary")
        _write_skill(bundled, "testing", "needs-glossary", skill_md)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            reg = SkillRegistry(
                user_home=tmp_path / "empty_home",
                populated_engagement_fields=set(),
            )
            active = reg.list_skills(only_active=True)
            assert not any(s.frontmatter.name == "needs-glossary" for s in active)

            reg2 = SkillRegistry(
                user_home=tmp_path / "empty_home",
                populated_engagement_fields={"glossary"},
            )
            active2 = reg2.list_skills(only_active=True)
            assert any(s.frontmatter.name == "needs-glossary" for s in active2)
        finally:
            loader_mod._bundled_skills_root = orig

    def test_mtime_reload(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            reg = SkillRegistry(user_home=tmp_path / "empty_home")
            skills1 = reg.list_skills(only_active=False)
            assert len(skills1) == 1

            # Add a new skill
            import time

            time.sleep(0.05)  # Ensure mtime changes
            new_md = VALID_SKILL_MD.replace("test-skill", "new-skill")
            _write_skill(bundled, "testing", "new-skill", new_md)

            skills2 = reg.list_skills(only_active=False)
            assert len(skills2) == 2
        finally:
            loader_mod._bundled_skills_root = orig


# ---------------------------------------------------------------------------
# Manage
# ---------------------------------------------------------------------------


class TestManage:
    def test_create_skill(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        path = create_skill(
            engagement_path=engagement,
            name="my-pattern",
            category="requirements",
            description="A test pattern",
            body="# My Pattern\n\nProcedure...",
        )
        assert path.exists()
        assert path.name == "SKILL.md"
        text = path.read_text()
        assert "status: draft" in text
        assert "my-pattern" in text

    def test_create_duplicate_fails(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        create_skill(
            engagement_path=engagement,
            name="my-pattern",
            category="requirements",
            description="A test pattern",
            body="# Body",
        )
        with pytest.raises(SkillError, match="already exists"):
            create_skill(
                engagement_path=engagement,
                name="my-pattern",
                category="requirements",
                description="Duplicate",
                body="# Body",
            )

    def test_create_invalid_name(self, tmp_path: Path) -> None:
        with pytest.raises(SkillError, match="must match"):
            create_skill(
                engagement_path=tmp_path,
                name="BAD NAME",
                category="test",
                description="x",
                body="x",
            )

    def test_patch_skill(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        bundled = tmp_path / "bundled"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            path = patch_skill(
                engagement_path=engagement,
                name="test-skill",
                body="# Updated body",
            )
            assert path.exists()
            text = path.read_text()
            assert "status: draft" in text
            assert "Updated body" in text
        finally:
            loader_mod._bundled_skills_root = orig

    def test_delete_skill(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        create_skill(
            engagement_path=engagement,
            name="to-delete",
            category="test",
            description="Delete me",
            body="# Delete",
        )
        skill_dir = engagement / ".praxis" / "skills" / "test" / "to-delete"
        assert skill_dir.exists()

        delete_skill(engagement_path=engagement, name="to-delete")
        assert not skill_dir.exists()

    def test_delete_nonexistent_fails(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        with pytest.raises(SkillError, match="not found"):
            delete_skill(engagement_path=engagement, name="nonexistent")

    def test_promote_skill(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        create_skill(
            engagement_path=engagement,
            name="to-promote",
            category="test",
            description="Promote me",
            body="# Promote",
        )

        path = promote_skill(engagement_path=engagement, name="to-promote")
        text = path.read_text()
        assert "status: published" in text

    def test_promote_already_published_fails(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        create_skill(
            engagement_path=engagement,
            name="to-promote",
            category="test",
            description="x",
            body="# x",
        )
        promote_skill(engagement_path=engagement, name="to-promote")

        with pytest.raises(SkillError, match="already published"):
            promote_skill(engagement_path=engagement, name="to-promote")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class TestSkillTools:
    def test_skill_list_tool(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            ctx = _make_context()
            result = skill_list(ctx)
            assert "test-skill" in result.content
            assert len(result.data["skills"]) >= 1
        finally:
            loader_mod._bundled_skills_root = orig

    def test_skill_view_tool(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            ctx = _make_context()
            result = skill_view(ctx, name="test-skill")
            assert "Test Skill" in result.content
            assert result.data["skill"] == "test-skill"
        finally:
            loader_mod._bundled_skills_root = orig

    def test_skill_view_file(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        skill_dir = _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "ref.md").write_text("# Ref content")

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            ctx = _make_context()
            result = skill_view(ctx, name="test-skill", file="ref.md")
            assert "Ref content" in result.content
        finally:
            loader_mod._bundled_skills_root = orig

    def test_skill_view_not_found(self, tmp_path: Path) -> None:
        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: tmp_path / "empty"
        try:
            ctx = _make_context()
            result = skill_view(ctx, name="nonexistent")
            assert "not found" in result.content.lower()
        finally:
            loader_mod._bundled_skills_root = orig

    def test_skill_manage_create(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: tmp_path / "empty"
        try:
            ctx = _make_context(engagement_path=engagement)
            result = skill_manage(
                ctx,
                action="create",
                name="my-pattern",
                category="requirements",
                description="A test pattern",
                body="# My Pattern\n\nProcedure...",
            )
            assert "draft" in result.content.lower()
            assert result.data["status"] == "draft"
        finally:
            loader_mod._bundled_skills_root = orig

    def test_skill_manage_no_engagement(self) -> None:
        ctx = _make_context(engagement_path=None)
        result = skill_manage(ctx, action="create", name="x")
        assert "no engagement" in result.content.lower()

    def test_skill_manage_create_missing_fields(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        ctx = _make_context(engagement_path=engagement)
        result = skill_manage(ctx, action="create", name="x")
        assert "category is required" in result.content.lower()

    def test_skill_manage_create_missing_description(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        ctx = _make_context(engagement_path=engagement)
        result = skill_manage(ctx, action="create", name="x", category="test")
        assert "description is required" in result.content.lower()

    def test_skill_manage_create_missing_body(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        ctx = _make_context(engagement_path=engagement)
        result = skill_manage(ctx, action="create", name="x", category="test", description="d")
        assert "body is required" in result.content.lower()

    def test_skill_manage_patch(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        bundled = tmp_path / "bundled"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            ctx = _make_context(engagement_path=engagement)
            result = skill_manage(ctx, action="patch", name="test-skill", body="# Updated")
            assert "patched" in result.content.lower()
            assert result.data["status"] == "draft"
        finally:
            loader_mod._bundled_skills_root = orig

    def test_skill_manage_delete(self, tmp_path: Path) -> None:
        engagement = tmp_path / "engagement"
        engagement.mkdir()
        (engagement / ".praxis" / "skills").mkdir(parents=True)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: tmp_path / "empty"
        try:
            ctx = _make_context(engagement_path=engagement)
            # First create a skill
            skill_manage(
                ctx,
                action="create",
                name="to-delete",
                category="test",
                description="d",
                body="b",
            )
            # Then delete it
            result = skill_manage(ctx, action="delete", name="to-delete")
            assert "deleted" in result.content.lower()
        finally:
            loader_mod._bundled_skills_root = orig

    def test_skill_list_empty(self, tmp_path: Path) -> None:
        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: tmp_path / "empty"
        try:
            ctx = _make_context()
            result = skill_list(ctx)
            assert "no active skills" in result.content.lower()
        finally:
            loader_mod._bundled_skills_root = orig

    def test_skill_list_with_category_filter(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            ctx = _make_context()
            # Matching category
            result = skill_list(ctx, category="testing")
            assert "test-skill" in result.content

            # Non-matching category
            result2 = skill_list(ctx, category="nonexistent")
            assert "no active skills" in result2.content.lower()
        finally:
            loader_mod._bundled_skills_root = orig

    def test_skill_view_file_not_found(self, tmp_path: Path) -> None:
        bundled = tmp_path / "bundled"
        _write_skill(bundled, "testing", "test-skill", VALID_SKILL_MD)

        import praxis.skills.loader as loader_mod

        orig = loader_mod._bundled_skills_root
        loader_mod._bundled_skills_root = lambda: bundled
        try:
            ctx = _make_context()
            result = skill_view(ctx, name="test-skill", file="missing.md")
            assert "not found" in result.content.lower()
        finally:
            loader_mod._bundled_skills_root = orig
