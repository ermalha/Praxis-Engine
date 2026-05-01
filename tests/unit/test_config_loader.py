"""Tests for config loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from praxis.config.loader import (
    load_engagement_config,
    load_global_config,
    load_profile,
    resolve_model_config,
    save_global_config,
    save_profile,
)
from praxis.config.models import (
    EngagementConfig,
    GlobalConfig,
    LogLevel,
    ModelConfig,
    ProfileConfig,
    Provider,
)
from praxis.errors import ConfigError


class TestLoadGlobalConfig:
    def test_defaults_when_no_file(self, tmp_home: Path) -> None:
        cfg = load_global_config(home=tmp_home)
        assert cfg.default_profile == "default"
        assert cfg.log_level == LogLevel.INFO

    def test_from_yaml(self, tmp_home: Path) -> None:
        (tmp_home / "config.yaml").write_text(
            yaml.safe_dump({"log_level": "debug", "default_profile": "alice"})
        )
        cfg = load_global_config(home=tmp_home)
        assert cfg.log_level == LogLevel.DEBUG
        assert cfg.default_profile == "alice"

    def test_env_override(self, tmp_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_LOG_LEVEL", "error")
        cfg = load_global_config(home=tmp_home)
        assert cfg.log_level == LogLevel.ERROR

    def test_malformed_yaml_raises(self, tmp_home: Path) -> None:
        (tmp_home / "config.yaml").write_text(": bad: yaml: {{")
        with pytest.raises(ConfigError):
            load_global_config(home=tmp_home)


class TestSaveAndLoadGlobalConfig:
    def test_roundtrip(self, tmp_home: Path) -> None:
        cfg = GlobalConfig(default_profile="test", log_level=LogLevel.WARNING)
        save_global_config(cfg, home=tmp_home)
        loaded = load_global_config(home=tmp_home)
        assert loaded.default_profile == "test"
        assert loaded.log_level == LogLevel.WARNING


class TestLoadProfile:
    def test_missing_profile_raises(self, tmp_home: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_profile("nonexistent", home=tmp_home)

    def test_roundtrip(self, tmp_home: Path) -> None:
        profile = ProfileConfig(name="test-profile")
        save_profile(profile, home=tmp_home)
        loaded = load_profile("test-profile", home=tmp_home)
        assert loaded.name == "test-profile"


class TestLoadEngagementConfig:
    def test_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="No engagement config"):
            load_engagement_config(tmp_path)

    def test_loads_valid(self, tmp_path: Path) -> None:
        praxis_dir = tmp_path / ".praxis"
        praxis_dir.mkdir()
        (praxis_dir / "config.yaml").write_text(
            yaml.safe_dump({"name": "Test", "methodology": "agile"})
        )
        cfg = load_engagement_config(tmp_path)
        assert cfg.name == "Test"
        assert cfg.methodology.value == "agile"


class TestResolveModelConfig:
    def _profile_with_aliases(self) -> ProfileConfig:
        return ProfileConfig(
            name="test",
            default_model_alias="default",
            model_aliases={
                "default": ModelConfig(
                    provider=Provider.ANTHROPIC,
                    model="claude-sonnet-4-20250514",
                    api_key_env="ANTHROPIC_API_KEY",
                ),
                "fast": ModelConfig(
                    provider=Provider.OPENAI,
                    model="gpt-4o-mini",
                    api_key_env="OPENAI_API_KEY",
                ),
            },
        )

    def test_uses_profile_default(self) -> None:
        profile = self._profile_with_aliases()
        mc = resolve_model_config(profile)
        assert mc.model == "claude-sonnet-4-20250514"

    def test_engagement_overrides_profile(self) -> None:
        profile = self._profile_with_aliases()
        eng = EngagementConfig(name="test", model_alias="fast")
        mc = resolve_model_config(profile, engagement=eng)
        assert mc.model == "gpt-4o-mini"

    def test_cli_overrides_everything(self) -> None:
        profile = self._profile_with_aliases()
        eng = EngagementConfig(name="test", model_alias="fast")
        mc = resolve_model_config(profile, engagement=eng, cli_alias="default")
        assert mc.model == "claude-sonnet-4-20250514"

    def test_missing_alias_raises(self) -> None:
        profile = self._profile_with_aliases()
        with pytest.raises(ConfigError, match="not found"):
            resolve_model_config(profile, cli_alias="nonexistent")
