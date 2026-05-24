"""D-066 — ``praxis doctor`` first-run health check.

Covers the 10 check functions in isolation + the CLI runner (table /
JSON / strict). The legacy ``transport.probe()`` behavior is preserved
behind ``praxis doctor probe`` and exercised by a back-compat test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.cli.doctor_checks import (
    CheckResult,
    check_active_profile,
    check_api_key_env,
    check_audit_writable,
    check_bundled_skills,
    check_engagement,
    check_model_alias,
    check_optional_extras,
    check_praxis_version,
    check_python_version,
    check_sqlite_state,
    run_all_checks,
)
from praxis.config.engagement import init_engagement
from praxis.config.loader import save_global_config, save_profile
from praxis.config.models import GlobalConfig, ModelConfig, Provider
from praxis.config.profiles import create_profile

runner = CliRunner()


def _setup_profile(name: str = "doctortest") -> str:
    profile = create_profile(name)
    profile.model_aliases["default"] = ModelConfig(
        provider=Provider.OPENAI, model="gpt-test", api_key_env="OPENAI_API_KEY"
    )
    profile.default_model_alias = "default"
    save_profile(profile)
    save_global_config(GlobalConfig(default_profile=name))
    return name


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


class TestPerCheckFunctions:
    def test_python_version_ok_on_supported(self) -> None:
        r = check_python_version()
        assert r.status == "ok"
        assert r.detail.startswith("3.")

    def test_praxis_version_is_informational(self) -> None:
        r = check_praxis_version()
        assert r.status == "ok"
        assert r.detail  # non-empty version string

    def test_active_profile_passes_when_profile_exists(self, tmp_home: Path) -> None:
        _setup_profile()
        r = check_active_profile()
        assert r.status == "ok"
        assert "doctortest" in r.detail

    def test_active_profile_fails_when_none_configured(self, tmp_home: Path) -> None:
        # tmp_home wipes any global config; no profile created.
        r = check_active_profile()
        assert r.status == "fail"

    def test_model_alias_passes(self, tmp_home: Path) -> None:
        _setup_profile()
        r = check_model_alias()
        assert r.status == "ok"
        assert "gpt-test" in r.detail

    def test_api_key_env_fails_when_env_missing(
        self, tmp_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_profile()
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        r = check_api_key_env()
        assert r.status == "fail"
        assert "OPENAI_API_KEY" in r.detail

    def test_api_key_env_passes_when_env_set(
        self, tmp_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _setup_profile()
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        r = check_api_key_env()
        assert r.status == "ok"

    def test_engagement_skip_when_none(self) -> None:
        r = check_engagement(None)
        assert r.status == "skip"

    def test_engagement_ok_when_valid(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        r = check_engagement(tmp_engagement)
        assert r.status == "ok"

    def test_engagement_fail_when_path_lacks_praxis_dir(self, tmp_path: Path) -> None:
        r = check_engagement(tmp_path)
        assert r.status == "fail"
        assert "lacks .praxis/" in r.detail

    def test_sqlite_state_skip_without_engagement(self) -> None:
        r = check_sqlite_state(None)
        assert r.status == "skip"

    def test_sqlite_state_passes_after_init(self, tmp_engagement: Path, tmp_home: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        # Trigger DB creation by running a workqueue write — init alone
        # may not create praxis.db.
        from praxis.workqueue.models import WorkItemPriority, WorkItemType
        from praxis.workqueue.repo import WorkQueueRepo

        WorkQueueRepo(tmp_engagement).enqueue(
            type=WorkItemType.REVIEW_ARTIFACT,
            assignee="agent",
            title="t",
            description="d",
            priority=WorkItemPriority.MEDIUM,
        )
        r = check_sqlite_state(tmp_engagement)
        assert r.status == "ok"

    def test_audit_writable_passes(self, tmp_home: Path) -> None:
        r = check_audit_writable()
        assert r.status == "ok"

    def test_bundled_skills_passes_or_warns(self) -> None:
        r = check_bundled_skills()
        # Either ok (skills are bundled) or warn (none discovered).
        assert r.status in ("ok", "warn")

    def test_optional_extras_reports_installed(self) -> None:
        r = check_optional_extras()
        # Whatever the state, the detail must mention "installed" / "not installed".
        assert "installed" in r.detail
        assert r.status in ("ok", "warn")


# ---------------------------------------------------------------------------
# Runner returns the right number of rows
# ---------------------------------------------------------------------------


class TestRunAllChecks:
    def test_runner_returns_ten_results(self, tmp_home: Path) -> None:
        results = run_all_checks()
        assert len(results) == 10
        for r in results:
            assert isinstance(r, CheckResult)
            assert r.status in ("ok", "warn", "fail", "skip")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestDoctorCLI:
    def test_cli_table_runs_without_engagement(self, tmp_home: Path) -> None:
        _setup_profile()
        # A missing API key would fail the run; supply one.
        import os

        os.environ["OPENAI_API_KEY"] = "sk-test"
        try:
            result = runner.invoke(app, ["doctor"])
            # Some checks (engagement, sqlite_state) skip; no fails expected.
            assert result.exit_code == 0, result.output
            assert "doctor" in result.output.lower()
        finally:
            os.environ.pop("OPENAI_API_KEY", None)

    def test_cli_json_parses_to_list_of_results(self, tmp_home: Path) -> None:
        _setup_profile()
        import os

        os.environ["OPENAI_API_KEY"] = "sk-test"
        try:
            result = runner.invoke(app, ["doctor", "--json"])
            assert result.exit_code == 0, result.output
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert len(data) == 10
            for entry in data:
                assert {"name", "status", "detail"} <= entry.keys()
        finally:
            os.environ.pop("OPENAI_API_KEY", None)

    def test_cli_fails_exit_code_when_critical_check_fails(self, tmp_home: Path) -> None:
        # No profile setup => active_profile + model_alias + api_key_env fail.
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 1

    def test_cli_strict_exits_nonzero_on_warning(
        self, tmp_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Force a 'warn' result and confirm --strict promotes it to exit 1."""
        _setup_profile()
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        # Patch ``load_bundled_skills`` at its source — ``doctor_checks``
        # lazy-imports it inside the check function, so the symbol isn't
        # bound at module level on ``praxis.cli.doctor_checks`` itself.
        def empty_skills() -> list[object]:
            return []

        monkeypatch.setattr("praxis.skills.load_bundled_skills", empty_skills)

        # Without strict: warn doesn't trip exit code (assuming no other fails).
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0, result.output

        # With strict: same setup must exit 1.
        result_strict = runner.invoke(app, ["doctor", "--strict"])
        assert result_strict.exit_code == 1


class TestDoctorProbeBackCompat:
    def test_probe_subcommand_still_exists(self, tmp_home: Path) -> None:
        """The original v0.3.x LLM-probe behavior must remain accessible
        as ``praxis doctor probe`` for users who scripted against it."""
        _setup_profile()

        # We don't want to make a real LLM call — patch probe to return
        # a successful ProbeResult so the command path runs end-to-end.
        from praxis.transport import models as transport_models
        from praxis.transport import openai_adapter as oai

        class FakeProbe:
            def probe(self) -> transport_models.ProbeResult:
                return transport_models.ProbeResult(
                    ok=True,
                    provider="openai",
                    model="gpt-test",
                    latency_ms=42.0,
                )

        import os

        os.environ["OPENAI_API_KEY"] = "sk-test"
        try:
            from unittest.mock import patch

            with patch.object(oai, "OpenAITransport", lambda *a, **k: FakeProbe()):
                result = runner.invoke(app, ["doctor", "probe"])
            assert result.exit_code == 0, result.output
            assert "ok" in result.output.lower() or "42" in result.output
        finally:
            os.environ.pop("OPENAI_API_KEY", None)
