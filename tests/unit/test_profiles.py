"""Tests for profile lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.config.profiles import (
    create_profile,
    delete_profile,
    get_active_profile_name,
    list_profiles,
)
from praxis.errors import ConfigError


class TestCreateProfile:
    def test_creates_profile_dir(self, tmp_home: Path) -> None:
        profile = create_profile("alice", home=tmp_home)
        assert profile.name == "alice"
        assert (tmp_home / "profiles" / "alice" / "profile.yaml").exists()

    def test_duplicate_raises(self, tmp_home: Path) -> None:
        create_profile("alice", home=tmp_home)
        with pytest.raises(ConfigError, match="already exists"):
            create_profile("alice", home=tmp_home)

    def test_invalid_name_raises(self, tmp_home: Path) -> None:
        with pytest.raises(ConfigError, match="Invalid profile name"):
            create_profile("Bad Name!", home=tmp_home)

    def test_name_allows_hyphens_underscores(self, tmp_home: Path) -> None:
        profile = create_profile("my-test_01", home=tmp_home)
        assert profile.name == "my-test_01"


class TestListProfiles:
    def test_empty(self, tmp_home: Path) -> None:
        assert list_profiles(home=tmp_home) == []

    def test_lists_created(self, tmp_home: Path) -> None:
        create_profile("alice", home=tmp_home)
        create_profile("bob", home=tmp_home)
        profiles = list_profiles(home=tmp_home)
        assert profiles == ["alice", "bob"]


class TestDeleteProfile:
    def test_deletes_existing(self, tmp_home: Path) -> None:
        create_profile("alice", home=tmp_home)
        delete_profile("alice", home=tmp_home, force=True)
        assert list_profiles(home=tmp_home) == []

    def test_nonexistent_raises(self, tmp_home: Path) -> None:
        with pytest.raises(ConfigError, match="does not exist"):
            delete_profile("ghost", home=tmp_home)

    def test_refuses_active_without_force(
        self, tmp_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create_profile("default", home=tmp_home)
        # default is the active profile
        with pytest.raises(ConfigError, match="active profile"):
            delete_profile("default", home=tmp_home)

    def test_force_deletes_active(self, tmp_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        create_profile("default", home=tmp_home)
        delete_profile("default", home=tmp_home, force=True)
        assert "default" not in list_profiles(home=tmp_home)


class TestGetActiveProfileName:
    def test_defaults_to_default(self, tmp_home: Path) -> None:
        assert get_active_profile_name(home=tmp_home) == "default"

    def test_env_override(self, tmp_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_PROFILE", "custom")
        assert get_active_profile_name(home=tmp_home) == "custom"
