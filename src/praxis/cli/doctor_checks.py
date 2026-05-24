"""Health-check functions for ``praxis doctor`` (D-066).

Each check is a pure function returning a :class:`CheckResult`. The
runner in ``doctor_cmd.py`` iterates them, collects results, and
renders a status table or a JSON report.

Status semantics:

- ``ok``    — check passed.
- ``warn``  — non-critical issue; user should know but the product still
              works.
- ``fail``  — critical issue; will block normal use.
- ``skip``  — check didn't apply in this context (e.g. SQLite check
              when no engagement is configured).
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from praxis import __version__ as _praxis_version

CheckStatus = Literal["ok", "warn", "fail", "skip"]


class CheckResult(BaseModel):
    """One row of the doctor report."""

    name: str
    status: CheckStatus
    detail: str


_OPTIONAL_EXTRAS = [
    ("anthropic", "anthropic"),
    ("openai", "openai"),
    ("tui", "textual"),
    ("jira", "atlassian"),
    ("confluence", "atlassian"),
    ("email", "imap_tools"),
    ("webhook", "fastapi"),
]


# ---------------------------------------------------------------------------
# Environment checks
# ---------------------------------------------------------------------------


def check_python_version() -> CheckResult:
    """Praxis requires Python 3.11+; warn (don't fail) on a major-version drift."""
    v = sys.version_info
    detail = f"{v.major}.{v.minor}.{v.micro}"
    if v.major != 3 or v.minor < 11:
        return CheckResult(
            name="python_version",
            status="fail",
            detail=f"{detail} (requires 3.11+)",
        )
    return CheckResult(name="python_version", status="ok", detail=detail)


def check_praxis_version() -> CheckResult:
    """Always informational; surfaces the running praxis version."""
    return CheckResult(name="praxis_version", status="ok", detail=_praxis_version)


# ---------------------------------------------------------------------------
# Profile + model checks
# ---------------------------------------------------------------------------


def check_active_profile(profile_name: str | None = None) -> CheckResult:
    """Active profile resolves and loads."""
    from praxis.config import load_profile
    from praxis.config.profiles import get_active_profile_name
    from praxis.errors import ConfigError

    try:
        resolved = profile_name or get_active_profile_name()
    except ConfigError as exc:
        return CheckResult(
            name="active_profile",
            status="fail",
            detail=f"No active profile set: {exc}",
        )

    try:
        load_profile(resolved)
    except ConfigError as exc:
        return CheckResult(
            name="active_profile",
            status="fail",
            detail=f"Cannot load profile {resolved!r}: {exc}",
        )

    return CheckResult(name="active_profile", status="ok", detail=resolved)


def check_model_alias(profile_name: str | None = None) -> CheckResult:
    """Default model alias resolves to a model_config."""
    from praxis.config import load_profile, resolve_model_config
    from praxis.config.profiles import get_active_profile_name
    from praxis.errors import ConfigError

    try:
        resolved = profile_name or get_active_profile_name()
        profile = load_profile(resolved)
        mc = resolve_model_config(profile)
    except ConfigError as exc:
        return CheckResult(
            name="model_alias",
            status="fail",
            detail=f"Cannot resolve model: {exc}",
        )

    return CheckResult(
        name="model_alias",
        status="ok",
        detail=f"{mc.provider}/{mc.model}",
    )


def check_api_key_env(profile_name: str | None = None) -> CheckResult:
    """Env var named by ``model_config.api_key_env`` is set + non-empty."""
    from praxis.config import load_profile, resolve_model_config
    from praxis.config.profiles import get_active_profile_name
    from praxis.errors import ConfigError

    try:
        resolved = profile_name or get_active_profile_name()
        profile = load_profile(resolved)
        mc = resolve_model_config(profile)
    except ConfigError:
        return CheckResult(
            name="api_key_env",
            status="skip",
            detail="(profile/model not resolvable; see other checks)",
        )

    env_var = mc.api_key_env
    if not env_var:
        return CheckResult(
            name="api_key_env",
            status="skip",
            detail="No api_key_env required (likely a local provider)",
        )
    value = os.environ.get(env_var)
    if not value:
        return CheckResult(
            name="api_key_env",
            status="fail",
            detail=f"Env var ${env_var} not set or empty",
        )
    return CheckResult(name="api_key_env", status="ok", detail=f"${env_var} is set")


# ---------------------------------------------------------------------------
# Engagement-scoped checks
# ---------------------------------------------------------------------------


def check_engagement(engagement_path: Path | None) -> CheckResult:
    """If an engagement was passed (or found via cwd), confirm ``.praxis/`` exists."""
    if engagement_path is None:
        return CheckResult(
            name="engagement",
            status="skip",
            detail="No engagement found in CWD; pass -e <path> to include",
        )
    praxis_dir = engagement_path / ".praxis"
    if not praxis_dir.is_dir():
        return CheckResult(
            name="engagement",
            status="fail",
            detail=f"Path lacks .praxis/: {engagement_path}",
        )
    return CheckResult(
        name="engagement",
        status="ok",
        detail=str(engagement_path),
    )


def check_sqlite_state(engagement_path: Path | None) -> CheckResult:
    """Open the engagement's praxis.db and run ``SELECT 1``."""
    if engagement_path is None:
        return CheckResult(
            name="sqlite_state",
            status="skip",
            detail="(no engagement)",
        )
    db_path = engagement_path / ".praxis" / "state" / "praxis.db"
    if not db_path.exists():
        return CheckResult(
            name="sqlite_state",
            status="warn",
            detail=f"praxis.db not yet created at {db_path}",
        )
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return CheckResult(
            name="sqlite_state",
            status="fail",
            detail=f"SELECT 1 failed: {exc}",
        )
    return CheckResult(name="sqlite_state", status="ok", detail=str(db_path))


def check_audit_writable() -> CheckResult:
    """Atomic-write a tiny test file into ``$PRAXIS_HOME`` (or ``~/.praxis/``)."""
    from praxis.storage.files import atomic_write_text

    home = Path(os.environ.get("PRAXIS_HOME", str(Path.home() / ".praxis")))
    try:
        home.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix="doctor-", suffix=".tmp", dir=str(home), delete=False
        ) as f:
            tmp_path = Path(f.name)
        try:
            atomic_write_text(tmp_path, "doctor-probe")
            tmp_path.unlink()
        except Exception:  # noqa: BLE001 — bubble up via fail result
            if tmp_path.exists():
                tmp_path.unlink()
            raise
    except OSError as exc:
        return CheckResult(
            name="audit_writable",
            status="fail",
            detail=f"Cannot write to {home}: {exc}",
        )
    return CheckResult(name="audit_writable", status="ok", detail=str(home))


# ---------------------------------------------------------------------------
# Skills + extras
# ---------------------------------------------------------------------------


def check_bundled_skills() -> CheckResult:
    """Confirm bundled skills are discoverable."""
    from praxis.skills import load_bundled_skills

    try:
        skills = load_bundled_skills()
    except Exception as exc:  # noqa: BLE001 — surface as fail
        return CheckResult(
            name="bundled_skills",
            status="fail",
            detail=f"Discovery failed: {exc}",
        )
    if not skills:
        return CheckResult(
            name="bundled_skills",
            status="warn",
            detail="No bundled skills found",
        )
    return CheckResult(
        name="bundled_skills",
        status="ok",
        detail=f"{len(skills)} discovered",
    )


def check_optional_extras() -> CheckResult:
    """Report which optional-extra packages are installed."""
    installed: list[str] = []
    missing: list[str] = []
    for extra, module_name in _OPTIONAL_EXTRAS:
        try:
            importlib.import_module(module_name)
            installed.append(extra)
        except ImportError:
            missing.append(extra)
    detail = (
        f"installed: {', '.join(installed) or 'none'} | "
        f"not installed: {', '.join(missing) or 'none'}"
    )
    # Never fail — extras are optional by definition. Warn only if NONE of
    # the LLM extras are present (anthropic / openai / tui), since the
    # product is hard to use without any of them.
    has_any_llm = any(e in installed for e in ("anthropic", "openai"))
    status: CheckStatus = "ok" if has_any_llm else "warn"
    if not has_any_llm:
        detail = f"No LLM extras installed (anthropic / openai). {detail}"
    return CheckResult(name="optional_extras", status=status, detail=detail)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_all_checks(
    *,
    profile_name: str | None = None,
    engagement_path: Path | None = None,
) -> list[CheckResult]:
    """Run every doctor check and return the results in display order."""
    return [
        check_python_version(),
        check_praxis_version(),
        check_active_profile(profile_name),
        check_model_alias(profile_name),
        check_api_key_env(profile_name),
        check_engagement(engagement_path),
        check_sqlite_state(engagement_path),
        check_audit_writable(),
        check_bundled_skills(),
        check_optional_extras(),
    ]
