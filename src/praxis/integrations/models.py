"""Models for the integration subsystem."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthStatus(StrEnum):
    """Result of a health check."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


class HealthResult(BaseModel):
    """Outcome of an integration health check."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1

    kind: str
    status: HealthStatus
    message: str = ""
    details: dict[str, object] = {}
