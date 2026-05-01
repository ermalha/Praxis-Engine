"""Profile lifecycle management.

Profiles live under ``~/.praxis/profiles/<name>/`` and are the user-identity
scope in Praxis.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from praxis.audit import emit
from praxis.errors import ConfigError

from .loader import _praxis_home, load_global_config, save_profile
from .models import ProfileConfig

_PROFILE_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


def _validate_profile_name(name: str) -> None:
    """Ensure *name* matches ``[a-z0-9_-]+``."""
    if not _PROFILE_NAME_RE.match(name):
        raise ConfigError(
            f"Invalid profile name '{name}'. Must match [a-z0-9_-]+.",
            name=name,
        )


def create_profile(name: str, home: Path | None = None) -> ProfileConfig:
    """Create a new profile directory with default settings.

    Args:
        name: Profile name (must match ``[a-z0-9_-]+``).
        home: Override for the ``~/.praxis`` directory.

    Returns:
        The newly created :class:`ProfileConfig`.

    Raises:
        ConfigError: If the name is invalid or already exists.
    """
    _validate_profile_name(name)
    praxis_home = _praxis_home(home)
    profile_dir = praxis_home / "profiles" / name
    if profile_dir.exists():
        raise ConfigError(f"Profile '{name}' already exists", name=name)

    profile = ProfileConfig(name=name)
    save_profile(profile, home=praxis_home)

    emit(
        "profile.created",
        profile=name,
        subject_id=name,
    )
    return profile


def list_profiles(home: Path | None = None) -> list[str]:
    """List all profile names.

    Args:
        home: Override for the ``~/.praxis`` directory.
    """
    praxis_home = _praxis_home(home)
    profiles_dir = praxis_home / "profiles"
    if not profiles_dir.exists():
        return []
    return sorted(
        d.name for d in profiles_dir.iterdir() if d.is_dir() and (d / "profile.yaml").exists()
    )


def delete_profile(name: str, home: Path | None = None, *, force: bool = False) -> None:
    """Delete a profile.

    Args:
        name: Profile name.
        home: Override for the ``~/.praxis`` directory.
        force: If ``False`` and the profile is the active one, refuse.

    Raises:
        ConfigError: If the profile doesn't exist, or is active without *force*.
    """
    _validate_profile_name(name)
    praxis_home = _praxis_home(home)
    profile_dir = praxis_home / "profiles" / name
    if not profile_dir.exists():
        raise ConfigError(f"Profile '{name}' does not exist", name=name)

    if not force:
        active = get_active_profile_name(home=praxis_home)
        if active == name:
            raise ConfigError(
                f"Profile '{name}' is the active profile. Use --force to delete it anyway.",
                name=name,
            )

    shutil.rmtree(profile_dir)

    emit(
        "profile.deleted",
        profile=name,
        subject_id=name,
    )


def get_active_profile_name(home: Path | None = None) -> str:
    """Return the active profile name.

    Resolution: ``PRAXIS_PROFILE`` env var → ``default_profile`` from global
    config → ``"default"``.

    Args:
        home: Override for the ``~/.praxis`` directory.
    """
    env_profile = os.environ.get("PRAXIS_PROFILE")
    if env_profile:
        return env_profile
    try:
        global_cfg = load_global_config(home=home)
        return global_cfg.default_profile
    except ConfigError:
        return "default"
