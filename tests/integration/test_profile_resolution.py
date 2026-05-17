"""Integration tests for active-default profile resolution (D-029).

Closes RW-001: ``check`` (and 5 sibling BA-surface commands) defaulted
``--profile`` to the literal string ``"default"``, so users without an
explicit ``--profile`` flag got ``Profile 'default' not found.`` even
with an active default profile configured. Each command must now resolve
via ``get_active_profile_name()`` when ``--profile`` is omitted.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.config.profiles import create_profile
from praxis.core.chat_runtime import ChatRuntime

from .conftest import StubTransport

runner = CliRunner()


class TestProfileResolution:
    """All BA-surface commands resolve the active default when --profile omitted."""

    def test_ask_resolves_active_default(
        self,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        result = runner.invoke(app, ["ask", "hello"])
        assert result.exit_code == 0, result.output
        assert "Profile 'default' not found" not in result.output

    def test_doctor_resolves_active_default(
        self,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Doctor calls transport.probe(); we stub make_transport but not probe.
        # Patch the stub instance to expose a passing probe.
        from praxis.transport.base import ProbeResult

        def fake_probe(self: StubTransport) -> ProbeResult:
            return ProbeResult(ok=True, latency_ms=1.0, provider="openai", model="gpt-test")

        monkeypatch.setattr(StubTransport, "probe", fake_probe, raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0, result.output
        assert "Profile 'default' not found" not in result.output

    def test_check_resolves_active_default(
        self,
        tmp_engagement: Path,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        init_engagement(tmp_engagement, "Test")
        # Provide a transport response shape acceptable to sufficiency parser.
        # If sufficiency parsing fails downstream we still verify profile
        # resolution happened (exit not 1 with the specific message).
        result = runner.invoke(
            app,
            ["check", "spec", "test target", "-e", str(tmp_engagement)],
        )
        assert "Profile 'default' not found" not in result.output

    def test_artifact_generate_resolves_active_default(
        self,
        tmp_engagement: Path,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        init_engagement(tmp_engagement, "Test")
        result = runner.invoke(
            app,
            ["artifact", "generate", "scope-brief", "-e", str(tmp_engagement)],
        )
        assert "Profile 'default' not found" not in result.output

    def test_elicit_resolves_active_default(
        self,
        tmp_engagement: Path,
        stub_transport: StubTransport,
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        init_engagement(tmp_engagement, "Test")
        # Without a sufficiency report present we expect a clean "no reports"
        # error — NOT the profile error. That's the regression check.
        result = runner.invoke(
            app,
            ["elicit", "--latest", "-e", str(tmp_engagement)],
        )
        assert "Profile 'default' not found" not in result.output
        assert "Profile 'realworld' not found" not in result.output

    def test_chat_resolves_active_default(
        self,
        tmp_engagement: Path,
        stub_transport: StubTransport,  # noqa: ARG002 — keeps profile env consistent
        realworld_profile: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``chat`` is interactive; bypass CliRunner and test the function call
        path directly to confirm it resolves the active default profile."""
        from praxis.cli.chat_cmd import chat as chat_func

        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        init_engagement(tmp_engagement, "Test")

        captured: dict[str, str | None] = {}

        @classmethod  # type: ignore[misc]
        def fake_create(
            cls: type[ChatRuntime],
            *,
            profile_name: str = "default",
            engagement_path: Path | None = None,
            model_alias: str | None = None,
            approval_callback: object | None = None,
            transport: object | None = None,
            agent_factory: object | None = None,
        ) -> object:
            captured["profile_name"] = profile_name
            raise RuntimeError("stop after profile resolution")

        monkeypatch.setattr(ChatRuntime, "create", fake_create)

        # chat catches the RuntimeError and converts to typer.Exit(1).
        # We don't care about the exit type; we care that fake_create saw
        # the resolved profile name.
        with contextlib.suppress(BaseException):
            chat_func(
                profile=None,
                engagement=str(tmp_engagement),
                model_alias=None,
            )
        assert captured["profile_name"] == realworld_profile

    def test_explicit_profile_overrides_active_default(
        self,
        stub_transport: StubTransport,
        realworld_profile: str,
        tmp_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When --profile is supplied, it wins over the active default."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        # Create a second profile but DON'T set it as default
        from praxis.config.models import ModelConfig, Provider
        from praxis.config.profiles import save_profile

        other = create_profile("other")
        other.model_aliases["default"] = ModelConfig(
            provider=Provider.OPENAI,
            model="gpt-other",
            api_key_env="OPENAI_API_KEY",
        )
        other.default_model_alias = "default"
        save_profile(other)

        result = runner.invoke(app, ["ask", "-p", "other", "hello"])
        assert result.exit_code == 0, result.output
        # The stub captured the request; verify the model was 'gpt-other'
        assert len(stub_transport.requests) == 1
        assert stub_transport.requests[0].model == "gpt-other"
