"""Base class for all integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from praxis.config.models import IntegrationConfig
from praxis.integrations.models import HealthResult, HealthStatus


class Integration(ABC):
    """Abstract base for optional integrations.

    Each integration wraps an external service (Jira, Confluence, email, etc.)
    and exposes tools the agent can use.  Integrations are lazy-loaded and
    degrade gracefully when not configured.
    """

    name: str
    kind: str

    def __init__(self, config: IntegrationConfig) -> None:
        self._config = config

    @property
    def settings(self) -> dict[str, str]:
        return self._config.settings

    def is_enabled(self) -> bool:
        return self._config.enabled

    @abstractmethod
    def health_check(self) -> HealthResult:
        """Check connectivity to the external service."""

    def _disabled_result(self) -> HealthResult:
        return HealthResult(
            kind=self.kind,
            status=HealthStatus.DISABLED,
            message=f"{self.name} is disabled",
        )
