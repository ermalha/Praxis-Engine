"""Integration test for Chunk 06 — Skill System.

Tests the full lifecycle: list → view → create draft → verify hidden → promote.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.models import ProfileConfig
from praxis.skills import SkillRegistry, create_skill, promote_skill
from praxis.skills.tools import skill_list, skill_manage, skill_view
from praxis.tools import ToolContext

runner = CliRunner()


@pytest.fixture()
def skill_env(tmp_path: Path) -> tuple[Path, Path]:
    """Set up bundled skills and an engagement directory.

    Returns (bundled_root, engagement_path).
    """
    # Create a bundled skill
    bundled = tmp_path / "bundled"
    skill_dir = bundled / "_test" / "echo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: echo-skill\n"
        "category: _test\n"
        "description: A minimal test skill.\n"
        "when_to_use: Testing.\n"
        "requires_toolsets: []\n"
        "fallback_for_toolsets: []\n"
        "required_engagement_fields: []\n"
        "human_curated: true\n"
        "status: published\n"
        "schema_version: 1\n"
        "---\n\n"
        "# Echo Skill\n\nEcho body.\n"
    )

    # Create engagement
    engagement = tmp_path / "engagement"
    engagement.mkdir()
    (engagement / ".praxis" / "skills").mkdir(parents=True)
    (engagement / ".praxis" / "config.yaml").write_text(
        "schema_version: 1\nname: test-engagement\nmethodology: none\n"
    )

    return bundled, engagement


def _patch_bundled(monkeypatch: pytest.MonkeyPatch, bundled: Path) -> None:
    """Monkey-patch the bundled skills root."""
    import praxis.skills.loader as loader_mod

    monkeypatch.setattr(loader_mod, "_bundled_skills_root", lambda: bundled)


def _make_ctx(engagement: Path) -> ToolContext:
    return ToolContext(
        profile=ProfileConfig(name="test"),
        audit=MagicMock(),
        engagement_path=engagement,
    )


class TestSkillLifecycle:
    def test_full_lifecycle(
        self,
        skill_env: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        bundled, engagement = skill_env
        _patch_bundled(monkeypatch, bundled)

        # 1. List initially shows only the bundled echo-skill
        reg = SkillRegistry(
            engagement_path=engagement,
            user_home=tmp_path / "empty_home",
        )
        skills = reg.list_skills()
        assert any(s.frontmatter.name == "echo-skill" for s in skills)

        # 2. Agent (via tool) creates a draft
        ctx = _make_ctx(engagement)
        res = skill_manage(
            ctx,
            action="create",
            name="my-pattern",
            category="requirements",
            description="A test pattern",
            body="# My Pattern\n\nProcedure...",
        )
        assert "draft" in res.content.lower()
        draft_path = engagement / ".praxis" / "skills" / "requirements" / "my-pattern" / "SKILL.md"
        assert draft_path.exists()

        # 3. Default list does not include drafts
        reg2 = SkillRegistry(
            engagement_path=engagement,
            user_home=tmp_path / "empty_home",
        )
        skills = reg2.list_skills()
        assert not any(s.frontmatter.name == "my-pattern" for s in skills)

        # 4. List with all=True shows it
        skills = reg2.list_skills(only_active=False)
        assert any(s.frontmatter.name == "my-pattern" for s in skills)

        # 5. Promote
        promote_skill(engagement_path=engagement, name="my-pattern")

        # 6. Now it appears in active list
        reg3 = SkillRegistry(
            engagement_path=engagement,
            user_home=tmp_path / "empty_home",
        )
        skills = reg3.list_skills()
        assert any(s.frontmatter.name == "my-pattern" for s in skills)

    def test_skill_list_tool_returns_skills(
        self,
        skill_env: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bundled, engagement = skill_env
        _patch_bundled(monkeypatch, bundled)

        ctx = _make_ctx(engagement)
        result = skill_list(ctx)
        assert "echo-skill" in result.content

    def test_skill_view_tool_returns_body(
        self,
        skill_env: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bundled, engagement = skill_env
        _patch_bundled(monkeypatch, bundled)

        ctx = _make_ctx(engagement)
        result = skill_view(ctx, name="echo-skill")
        assert "Echo Skill" in result.content
        assert result.data["skill"] == "echo-skill"

    def test_cli_skill_promote(
        self,
        skill_env: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bundled, engagement = skill_env
        _patch_bundled(monkeypatch, bundled)

        # Create a draft
        create_skill(
            engagement_path=engagement,
            name="cli-test",
            category="test",
            description="CLI test skill",
            body="# CLI Test",
        )

        # Promote via CLI
        result = runner.invoke(
            app,
            ["skill", "promote", "cli-test", "--engagement", str(engagement), "-y"],
        )
        assert result.exit_code == 0
        assert "promoted" in result.output.lower()

    def test_cli_skill_list(
        self,
        skill_env: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bundled, engagement = skill_env
        _patch_bundled(monkeypatch, bundled)

        result = runner.invoke(
            app,
            ["skill", "list", "--engagement", str(engagement)],
        )
        assert result.exit_code == 0
        assert "echo-skill" in result.output
