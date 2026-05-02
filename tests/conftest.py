"""Praxis test fixtures.

Common fixtures used across unit, integration, and e2e tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.storage.db import close_connection


@pytest.fixture()
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide a temporary ``~/.praxis`` directory.

    Sets ``HOME`` and ``PRAXIS_HOME`` so all config/profile/audit operations
    are sandboxed to *tmp_path*.
    """
    praxis_home = tmp_path / ".praxis"
    praxis_home.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRAXIS_HOME", str(praxis_home))
    # Clear any profile override
    monkeypatch.delenv("PRAXIS_PROFILE", raising=False)
    return praxis_home


@pytest.fixture()
def tmp_engagement(tmp_path: Path, tmp_home: Path) -> Path:
    """Create a temporary engagement directory (not yet initialized).

    Returns the engagement root (the directory that will contain ``.praxis/``).
    """
    eng_dir = tmp_path / "test-engagement"
    eng_dir.mkdir()
    return eng_dir


@pytest.fixture()
def db_engagement(tmp_engagement: Path) -> Path:
    """Create and initialize a temporary engagement with SQLite database.

    Returns the engagement root with ``.praxis/state/praxis.db`` ready.
    """
    init_engagement(tmp_engagement, "Test Engagement")
    db_path = tmp_engagement / ".praxis" / "state" / "praxis.db"
    yield tmp_engagement
    close_connection(db_path)
