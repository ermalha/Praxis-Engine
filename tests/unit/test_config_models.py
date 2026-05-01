"""Tests for config Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from praxis.config.models import (
    EngagementConfig,
    GlobalConfig,
    IntegrationConfig,
    IntegrationKind,
    LogLevel,
    Methodology,
    ModelConfig,
    ProfileConfig,
    Provider,
    WakeCycleConfig,
    WakeCycleMode,
)


class TestGlobalConfig:
    def test_defaults(self) -> None:
        cfg = GlobalConfig()
        assert cfg.default_profile == "default"
        assert cfg.log_level == LogLevel.INFO
        assert cfg.default_model_alias is None
        assert cfg.audit_log_path is None

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            GlobalConfig(unknown_field="bad")  # type: ignore[call-arg]


class TestModelConfig:
    def test_minimal(self) -> None:
        mc = ModelConfig(
            provider=Provider.ANTHROPIC,
            model="claude-sonnet-4-20250514",
            api_key_env="ANTHROPIC_API_KEY",
        )
        assert mc.timeout_s == 120
        assert mc.extra_headers == {}
        assert mc.base_url is None

    def test_with_base_url(self) -> None:
        mc = ModelConfig(
            provider=Provider.OPENAI_COMPAT,
            model="local-model",
            api_key_env="LOCAL_KEY",
            base_url="http://localhost:8080/v1",
        )
        assert str(mc.base_url) == "http://localhost:8080/v1"


class TestProfileConfig:
    def test_minimal(self) -> None:
        pc = ProfileConfig(name="alice")
        assert pc.name == "alice"
        assert pc.model_aliases == {}
        assert pc.default_model_alias == "default"

    def test_with_model_aliases(self) -> None:
        pc = ProfileConfig(
            name="bob",
            model_aliases={
                "default": ModelConfig(
                    provider=Provider.OPENAI,
                    model="gpt-4o",
                    api_key_env="OPENAI_API_KEY",
                ),
            },
        )
        assert "default" in pc.model_aliases


class TestEngagementConfig:
    def test_defaults(self) -> None:
        ec = EngagementConfig(name="Test Project")
        assert ec.methodology == Methodology.NONE
        assert ec.model_alias is None
        assert ec.integrations == {}
        assert ec.wake_cycle.mode == WakeCycleMode.MANUAL

    def test_full(self) -> None:
        ec = EngagementConfig(
            name="Big Project",
            methodology=Methodology.SCRUM,
            model_alias="fast",
            integrations={
                "jira": IntegrationConfig(kind=IntegrationKind.JIRA, enabled=True),
            },
            wake_cycle=WakeCycleConfig(
                mode=WakeCycleMode.SCHEDULED,
                interval_minutes=30,
                quiet_hours=(22, 7),
            ),
        )
        assert ec.integrations["jira"].enabled is True
        assert ec.wake_cycle.quiet_hours == (22, 7)


class TestWakeCycleConfig:
    def test_defaults(self) -> None:
        wc = WakeCycleConfig()
        assert wc.mode == WakeCycleMode.MANUAL
        assert wc.interval_minutes == 15
        assert wc.quiet_hours is None
