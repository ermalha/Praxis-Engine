"""Chunk 02 acceptance test — full profile and engagement lifecycle via CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from praxis.cli import app

runner = CliRunner()


def test_full_profile_and_engagement_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: create profile, list, init engagement, show config, check audit."""
    home = tmp_path / ".praxis"
    home.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRAXIS_HOME", str(home))
    monkeypatch.delenv("PRAXIS_PROFILE", raising=False)

    # 1. Create profile
    result = runner.invoke(app, ["profile", "create", "alice"])
    assert result.exit_code == 0, result.output
    assert (home / "profiles" / "alice" / "profile.yaml").exists()

    # 2. List profiles includes alice
    result = runner.invoke(app, ["profile", "list", "--json"])
    assert result.exit_code == 0, result.output
    assert "alice" in result.output

    # 3. Init engagement
    eng = tmp_path / "myproj"
    eng.mkdir()
    result = runner.invoke(app, ["init", str(eng), "--name", "Demo Project"])
    assert result.exit_code == 0, result.output
    assert (eng / ".praxis" / "config.yaml").exists()
    assert (eng / ".praxis" / "engagement" / "glossary.yaml").exists()

    # 4. Resolved config picks up engagement
    result = runner.invoke(
        app,
        ["config", "show", "--profile", "alice", "--engagement", str(eng), "--json"],
    )
    assert result.exit_code == 0, result.output
    cfg = json.loads(result.output)
    assert cfg["engagement"]["name"] == "Demo Project"

    # 5. Audit log has events
    audit_file = home / "audit.jsonl"
    assert audit_file.exists()
    audit_lines = audit_file.read_text().splitlines()
    types = [json.loads(line)["event_type"] for line in audit_lines]
    assert "profile.created" in types
    assert "engagement.initialized" in types


def test_version_still_works() -> None:
    """Regression: version command from chunk 01 still works."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "praxis 0.3.1" in result.output


def test_init_duplicate_engagement_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / ".praxis"
    home.mkdir()
    monkeypatch.setenv("PRAXIS_HOME", str(home))

    eng = tmp_path / "proj"
    eng.mkdir()
    result = runner.invoke(app, ["init", str(eng), "--name", "First"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["init", str(eng), "--name", "Second"])
    assert result.exit_code == 1


def test_profile_create_invalid_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / ".praxis"
    home.mkdir()
    monkeypatch.setenv("PRAXIS_HOME", str(home))
    result = runner.invoke(app, ["profile", "create", "Bad Name!"])
    assert result.exit_code == 1
