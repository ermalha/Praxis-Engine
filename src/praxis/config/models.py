"""Configuration Pydantic models for Praxis.

All configuration is expressed as Pydantic v2 models with ``extra="forbid"``.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl  # noqa: TC002

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LogLevel(StrEnum):
    """Supported application log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Methodology(StrEnum):
    """Supported engagement methodologies."""

    AGILE = "agile"
    SCRUM = "scrum"
    KANBAN = "kanban"
    WATERFALL = "waterfall"
    HYBRID = "hybrid"
    NONE = "none"


class WakeCycleMode(StrEnum):
    """Orchestrator wake-cycle modes."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT_DRIVEN = "event_driven"
    MIXED = "mixed"


class IntegrationKind(StrEnum):
    """Known integration types."""

    JIRA = "jira"
    CONFLUENCE = "confluence"
    IMAP = "imap"
    SMTP = "smtp"
    WEBHOOK = "webhook"


class Provider(StrEnum):
    """LLM provider identifiers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    OPENAI_COMPAT = "openai_compat"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class WakeCycleConfig(BaseModel):
    """Orchestrator timing configuration."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    mode: WakeCycleMode = WakeCycleMode.MANUAL
    interval_minutes: int = 15
    quiet_hours: tuple[int, int] | None = None


class IntegrationConfig(BaseModel):
    """One integration's enable/disable + connection settings."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    enabled: bool = False
    kind: IntegrationKind
    settings: dict[str, str] = {}


class ModelConfig(BaseModel):
    """One LLM target preset."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    provider: Provider
    model: str
    base_url: HttpUrl | None = None
    api_key_env: str
    extra_headers: dict[str, str] = {}
    timeout_s: int = 120


# ---------------------------------------------------------------------------
# Top-level configs
# ---------------------------------------------------------------------------


class GlobalConfig(BaseModel):
    """Applies across all engagements for a profile."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    default_profile: str = "default"
    log_level: LogLevel = LogLevel.INFO
    default_model_alias: str | None = None
    audit_log_path: Path | None = None


class ProfileConfig(BaseModel):
    """Per-profile settings stored in ``~/.praxis/profiles/<name>/profile.yaml``."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    name: str
    display_name: str | None = None
    model_aliases: dict[str, ModelConfig] = {}
    default_model_alias: str = "default"


class EngagementConfig(BaseModel):
    """Per-engagement settings stored in ``<engagement>/.praxis/config.yaml``."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    name: str
    methodology: Methodology = Methodology.NONE
    model_alias: str | None = None
    integrations: dict[str, IntegrationConfig] = {}
    wake_cycle: WakeCycleConfig = WakeCycleConfig()
