"""Tool execution context."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from praxis.audit.models import AuditEvent
from praxis.config.models import EngagementConfig, GlobalConfig, ProfileConfig


@dataclass
class ToolContext:
    """Context injected as the first argument to every tool function.

    The agent constructs this once per turn.
    """

    profile: ProfileConfig
    engagement: EngagementConfig | None = None
    engagement_path: Path | None = None
    audit: Callable[..., AuditEvent] = field(default=lambda *_args: None, repr=False)  # type: ignore[assignment]
    db: sqlite3.Connection | None = None
    config: GlobalConfig = field(default_factory=GlobalConfig)
