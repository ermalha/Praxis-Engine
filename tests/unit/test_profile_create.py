"""Tests for enhanced ``praxis profile create`` CLI command (D-009, D-016)."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from praxis.cli import app

runner = CliRunner()


class TestProfileCreateCLI:
    """CLI-level tests for ``praxis profile create``."""

    def test_basic_create(self, tmp_home: Path) -> None:
        result = runner.invoke(app, ["profile", "create", "alice"])
        assert result.exit_code == 0
        assert "alice" in result.output

    def test_create_with_model_options(self, tmp_home: Path) -> None:
        result = runner.invoke(
            app,
            [
                "profile",
                "create",
                "alice",
                "--provider",
                "anthropic",
                "--model",
                "claude-sonnet-4-20250514",
                "--api-key-env",
                "ANTHROPIC_API_KEY",
            ],
        )
        assert result.exit_code == 0
        assert "alice" in result.output

        # Verify the model alias was written to profile.yaml
        profile_yaml = tmp_home / "profiles" / "alice" / "profile.yaml"
        assert profile_yaml.exists()
        data = yaml.safe_load(profile_yaml.read_text())
        assert "default" in data["model_aliases"]
        assert data["model_aliases"]["default"]["provider"] == "anthropic"
        assert data["model_aliases"]["default"]["model"] == "claude-sonnet-4-20250514"
        assert data["model_aliases"]["default"]["api_key_env"] == "ANTHROPIC_API_KEY"

    def test_auto_default_first_profile(self, tmp_home: Path) -> None:
        result = runner.invoke(app, ["profile", "create", "alice"])
        assert result.exit_code == 0
        assert "Auto-set as default" in result.output

        # Verify global config was updated
        config_yaml = tmp_home / "config.yaml"
        assert config_yaml.exists()
        data = yaml.safe_load(config_yaml.read_text())
        assert data["default_profile"] == "alice"

    def test_second_profile_not_auto_default(self, tmp_home: Path) -> None:
        runner.invoke(app, ["profile", "create", "alice"])
        result = runner.invoke(app, ["profile", "create", "bob"])
        assert result.exit_code == 0
        assert "Auto-set as default" not in result.output

        # Global config should still point to alice
        config_yaml = tmp_home / "config.yaml"
        data = yaml.safe_load(config_yaml.read_text())
        assert data["default_profile"] == "alice"

    def test_set_default_flag(self, tmp_home: Path) -> None:
        runner.invoke(app, ["profile", "create", "alice"])
        result = runner.invoke(app, ["profile", "create", "bob", "--set-default"])
        assert result.exit_code == 0

        config_yaml = tmp_home / "config.yaml"
        data = yaml.safe_load(config_yaml.read_text())
        assert data["default_profile"] == "bob"

    def test_no_model_shows_next_step(self, tmp_home: Path) -> None:
        result = runner.invoke(app, ["profile", "create", "alice"])
        assert result.exit_code == 0
        assert "Next:" in result.output or "--provider" in result.output

    def test_partial_model_options_no_alias(self, tmp_home: Path) -> None:
        """Only --provider without --model and --api-key-env should NOT create alias."""
        result = runner.invoke(app, ["profile", "create", "alice", "--provider", "anthropic"])
        assert result.exit_code == 0

        profile_yaml = tmp_home / "profiles" / "alice" / "profile.yaml"
        data = yaml.safe_load(profile_yaml.read_text())
        assert data["model_aliases"] == {}

    def test_duplicate_name_fails(self, tmp_home: Path) -> None:
        runner.invoke(app, ["profile", "create", "alice"])
        result = runner.invoke(app, ["profile", "create", "alice"])
        assert result.exit_code == 1
        assert "already exists" in result.output
