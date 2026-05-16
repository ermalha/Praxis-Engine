"""Tests for engagement lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.config.engagement import find_engagement, init_engagement, is_engagement
from praxis.errors import ConfigError


class TestInitEngagement:
    def test_creates_scaffold(self, tmp_engagement: Path) -> None:
        config = init_engagement(tmp_engagement, "Test Project")
        assert config.name == "Test Project"
        praxis_dir = tmp_engagement / ".praxis"
        assert (praxis_dir / "config.yaml").exists()
        assert (praxis_dir / "engagement" / "glossary.yaml").exists()
        assert (praxis_dir / "engagement" / "stakeholders.yaml").exists()
        assert (praxis_dir / "engagement" / "open-questions.yaml").exists()
        assert (praxis_dir / "engagement" / "assumptions-and-constraints.yaml").exists()
        assert (praxis_dir / "engagement" / "system-landscape.yaml").exists()
        assert (praxis_dir / "engagement" / "timeline.yaml").exists()
        assert (praxis_dir / "engagement" / "risks.yaml").exists()
        assert (praxis_dir / "engagement" / "lessons-learned.md").exists()
        assert (praxis_dir / "engagement" / "decisions").is_dir()
        assert (praxis_dir / "artifacts" / "stories").is_dir()
        assert (praxis_dir / "artifacts" / "specs").is_dir()
        assert (praxis_dir / "artifacts" / "models").is_dir()
        assert (praxis_dir / "artifacts" / "matrices").is_dir()
        assert (praxis_dir / "artifacts" / "reports").is_dir()
        assert (praxis_dir / "state").is_dir()
        assert (praxis_dir / "skills").is_dir()

    def test_with_methodology(self, tmp_engagement: Path) -> None:
        config = init_engagement(tmp_engagement, "Agile Proj", methodology="agile")
        assert config.methodology.value == "agile"

    def test_duplicate_raises(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "First")
        with pytest.raises(ConfigError, match="already initialized"):
            init_engagement(tmp_engagement, "Second")

    def test_invalid_methodology_raises(self, tmp_engagement: Path) -> None:
        with pytest.raises(ConfigError, match="Invalid methodology"):
            init_engagement(tmp_engagement, "Bad", methodology="xp")


class TestFindEngagement:
    def test_finds_from_root(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        assert find_engagement(tmp_engagement) == tmp_engagement

    def test_finds_from_subdirectory(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        sub = tmp_engagement / "deep" / "nested"
        sub.mkdir(parents=True)
        assert find_engagement(sub) == tmp_engagement

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        assert find_engagement(tmp_path / "nowhere") is None

    def test_ignores_plain_praxis_directory_without_config(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".praxis").mkdir()
        child = workspace / "child"
        child.mkdir()

        assert find_engagement(child) is None


class TestIsEngagement:
    def test_true_after_init(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        assert is_engagement(tmp_engagement) is True

    def test_false_before_init(self, tmp_engagement: Path) -> None:
        assert is_engagement(tmp_engagement) is False
