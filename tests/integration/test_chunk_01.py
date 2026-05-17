"""Chunk 01 acceptance test — project skeleton is importable and well-formed."""

import importlib
import subprocess
import sys

from praxis import PraxisError, __version__
from praxis.errors import (
    AuditError,
    ConfigError,
    EngagementError,
    SkillError,
    StorageError,
    SufficiencyError,
    ToolError,
    TransportError,
    WorkqueueError,
)


def test_version_string() -> None:
    assert __version__ == "0.3.0"


def test_all_error_classes_inherit_from_praxis_error() -> None:
    for cls in [
        ConfigError,
        StorageError,
        TransportError,
        ToolError,
        SkillError,
        EngagementError,
        WorkqueueError,
        SufficiencyError,
        AuditError,
    ]:
        assert issubclass(cls, PraxisError), f"{cls.__name__} must subclass PraxisError"


def test_error_details_kwarg() -> None:
    err = TransportError("timeout", provider="anthropic", status=503)
    assert err.details == {"provider": "anthropic", "status": 503}
    assert str(err) == "timeout"


def test_all_subsystem_packages_importable() -> None:
    subsystems = [
        "praxis.cli",
        "praxis.core",
        "praxis.transport",
        "praxis.engagement",
        "praxis.storage",
        "praxis.tools",
        "praxis.skills",
        "praxis.workqueue",
        "praxis.audit",
        "praxis.config",
        "praxis.integrations",
        "praxis.tui",
    ]
    for mod in subsystems:
        importlib.import_module(mod)


def test_cli_version_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "praxis", "version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "praxis 0.3.0" in result.stdout
