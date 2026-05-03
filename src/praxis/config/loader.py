"""Configuration loading and resolution.

Layered resolution order (lowest → highest precedence):
1. Pydantic model defaults
2. YAML files on disk
3. Environment variables (``PRAXIS_*``)
4. CLI flags (passed by caller)
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from praxis.errors import ConfigError

from .models import (
    EngagementConfig,
    GlobalConfig,
    ModelConfig,
    ProfileConfig,
)

_DEFAULT_HOME = Path.home() / ".praxis"


def _praxis_home(home: Path | None = None) -> Path:
    """Resolve the Praxis home directory."""
    if home is not None:
        return home
    return Path(os.environ.get("PRAXIS_HOME", str(_DEFAULT_HOME)))


def _read_yaml(path: Path) -> dict[str, object]:
    """Read a YAML file and return its contents as a dict."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Malformed YAML in {path}: {exc}", path=str(path)) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(
            f"Expected a mapping in {path}, got {type(data).__name__}",
            path=str(path),
        )
    return data


def _write_yaml_atomic(path: Path, data: dict[str, object]) -> None:
    """Atomically write *data* as YAML to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        f.flush()
        os.fsync(f.fileno())
    tmp.rename(path)


def load_global_config(home: Path | None = None) -> GlobalConfig:
    """Load global config from ``~/.praxis/config.yaml`` with env overlay.

    Args:
        home: Override for the ``~/.praxis`` directory (useful in tests).
    """
    praxis_home = _praxis_home(home)
    data = _read_yaml(praxis_home / "config.yaml")

    # Env var overlay
    env_level = os.environ.get("PRAXIS_LOG_LEVEL")
    if env_level is not None:
        data["log_level"] = env_level

    env_profile = os.environ.get("PRAXIS_DEFAULT_PROFILE")
    if env_profile is not None:
        data["default_profile"] = env_profile

    try:
        return GlobalConfig.model_validate(data)
    except Exception as exc:
        raise ConfigError(
            f"Invalid global config: {exc}",
            path=str(praxis_home / "config.yaml"),
        ) from exc


def load_profile(name: str, home: Path | None = None) -> ProfileConfig:
    """Load a profile from ``~/.praxis/profiles/<name>/profile.yaml``.

    Args:
        name: Profile name.
        home: Override for the ``~/.praxis`` directory.
    """
    praxis_home = _praxis_home(home)
    profile_path = praxis_home / "profiles" / name / "profile.yaml"
    if not profile_path.exists():
        raise ConfigError(f"Profile '{name}' not found", profile=name)
    data = _read_yaml(profile_path)
    data.setdefault("name", name)
    try:
        return ProfileConfig.model_validate(data)
    except Exception as exc:
        raise ConfigError(f"Invalid profile config for '{name}': {exc}", profile=name) from exc


def load_engagement_config(path: Path) -> EngagementConfig:
    """Load engagement config from ``<path>/.praxis/config.yaml``.

    Args:
        path: The engagement root directory.
    """
    config_path = path / ".praxis" / "config.yaml"
    if not config_path.exists():
        raise ConfigError(f"No engagement config at {config_path}", path=str(config_path))
    data = _read_yaml(config_path)
    try:
        return EngagementConfig.model_validate(data)
    except Exception as exc:
        raise ConfigError(f"Invalid engagement config: {exc}", path=str(config_path)) from exc


def resolve_model_config(
    profile: ProfileConfig,
    engagement: EngagementConfig | None = None,
    cli_alias: str | None = None,
) -> ModelConfig:
    """Resolve which ModelConfig to use.

    Precedence (highest first): *cli_alias* → engagement ``model_alias`` →
    profile ``default_model_alias``.

    Args:
        profile: The active profile config.
        engagement: The active engagement config (if any).
        cli_alias: Alias passed via CLI flag.

    Raises:
        ConfigError: If the resolved alias doesn't exist in the profile.
    """
    alias = cli_alias
    if alias is None and engagement is not None and engagement.model_alias is not None:
        alias = engagement.model_alias
    if alias is None:
        alias = profile.default_model_alias

    if alias not in profile.model_aliases:
        available = list(profile.model_aliases.keys())
        raise ConfigError(
            f"Model alias '{alias}' not found in profile '{profile.name}'. Available: {available}",
            alias=alias,
            profile=profile.name,
        )
    return profile.model_aliases[alias]


def save_engagement_config(path: Path, config: EngagementConfig) -> Path:
    """Persist engagement config to disk.

    Args:
        path: The engagement root directory.
        config: The config to write.

    Returns:
        The path the config was written to.
    """
    config_path = path / ".praxis" / "config.yaml"
    _write_yaml_atomic(config_path, config.model_dump(mode="json"))
    return config_path


def save_global_config(config: GlobalConfig, home: Path | None = None) -> Path:
    """Persist global config to disk.

    Args:
        config: The config to write.
        home: Override for the ``~/.praxis`` directory.

    Returns:
        The path the config was written to.
    """
    praxis_home = _praxis_home(home)
    path = praxis_home / "config.yaml"
    _write_yaml_atomic(path, config.model_dump(mode="json"))
    return path


def save_profile(profile: ProfileConfig, home: Path | None = None) -> Path:
    """Persist a profile config to disk.

    Args:
        profile: The profile to write.
        home: Override for the ``~/.praxis`` directory.

    Returns:
        The path the profile was written to.
    """
    praxis_home = _praxis_home(home)
    path = praxis_home / "profiles" / profile.name / "profile.yaml"
    _write_yaml_atomic(path, profile.model_dump(mode="json"))
    return path
