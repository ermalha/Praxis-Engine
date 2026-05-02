"""Engagement lifecycle management.

An engagement is a project/programme the analyst is working on.
State lives under ``<path>/.praxis/``.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from praxis.audit import emit
from praxis.errors import ConfigError
from praxis.storage.db import init_db

from .models import EngagementConfig, Methodology


def _write_yaml_atomic(path: Path, data: object) -> None:
    """Atomically write YAML to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        f.flush()
        os.fsync(f.fileno())
    tmp.rename(path)


def init_engagement(
    path: Path,
    name: str,
    *,
    methodology: str = "none",
) -> EngagementConfig:
    """Initialize a new engagement at *path*.

    Creates the full ``.praxis/`` directory scaffold with empty-but-valid
    YAML files.

    Args:
        path: Root directory for the engagement.
        name: Human-readable engagement name.
        methodology: One of the :class:`Methodology` values.

    Returns:
        The created :class:`EngagementConfig`.

    Raises:
        ConfigError: If the path already contains a ``.praxis/`` directory.
    """
    praxis_dir = path / ".praxis"
    if praxis_dir.exists():
        raise ConfigError(
            f"Engagement already initialized at {path}",
            path=str(path),
        )

    # Validate methodology
    try:
        meth = Methodology(methodology)
    except ValueError as exc:
        valid = [m.value for m in Methodology]
        raise ConfigError(
            f"Invalid methodology '{methodology}'. Valid: {valid}",
            methodology=methodology,
        ) from exc

    config = EngagementConfig(name=name, methodology=meth)

    # Create directory scaffold
    dirs = [
        praxis_dir / "engagement" / "decisions",
        praxis_dir / "artifacts" / "stories",
        praxis_dir / "artifacts" / "specs",
        praxis_dir / "artifacts" / "models",
        praxis_dir / "artifacts" / "matrices",
        praxis_dir / "artifacts" / "reports",
        praxis_dir / "state",
        praxis_dir / "skills",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Write config
    _write_yaml_atomic(
        praxis_dir / "config.yaml",
        config.model_dump(mode="json"),
    )

    # Write empty-but-valid engagement files
    _empty_files: dict[str, object] = {
        "engagement/glossary.yaml": {"terms": []},
        "engagement/stakeholders.yaml": {"stakeholders": []},
        "engagement/open-questions.yaml": {"questions": []},
        "engagement/assumptions-and-constraints.yaml": {
            "assumptions": [],
            "constraints": [],
        },
        "engagement/system-landscape.yaml": {"systems": []},
        "engagement/timeline.yaml": {"milestones": []},
        "engagement/risks.yaml": {"risks": []},
    }
    for rel_path, content in _empty_files.items():
        _write_yaml_atomic(praxis_dir / rel_path, content)

    # Lessons-learned is Markdown, not YAML
    lessons = praxis_dir / "engagement" / "lessons-learned.md"
    tmp = lessons.with_suffix(".tmp")
    tmp.write_text("# Lessons Learned\n")
    tmp.rename(lessons)

    # Initialize SQLite database with migrations
    db_path = praxis_dir / "state" / "praxis.db"
    init_db(db_path)

    emit(
        "engagement.initialized",
        engagement=name,
        engagement_path=path,
        subject_id=name,
        methodology=methodology,
    )

    return config


def find_engagement(start: Path) -> Path | None:
    """Walk up from *start* looking for a ``.praxis/`` directory.

    Returns the engagement root (parent of ``.praxis/``) or ``None``.
    """
    current = start.resolve()
    while True:
        if (current / ".praxis").is_dir():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def is_engagement(path: Path) -> bool:
    """Return ``True`` if *path* contains an initialized engagement."""
    return (path / ".praxis" / "config.yaml").is_file()
