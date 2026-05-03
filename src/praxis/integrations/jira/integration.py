"""Jira integration — connects Praxis to Jira Cloud/Server."""

from __future__ import annotations

from praxis.config.models import IntegrationConfig
from praxis.integrations.base import Integration
from praxis.integrations.models import HealthResult, HealthStatus
from praxis.integrations.registry import register_integration


@register_integration
class JiraIntegration(Integration):
    """Jira Cloud/Server integration."""

    name = "Jira"
    kind = "jira"

    def __init__(self, config: IntegrationConfig) -> None:
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from praxis.integrations.jira.client import JiraClient

            self._client = JiraClient.from_settings(self.settings)
        return self._client

    def health_check(self) -> HealthResult:
        if not self.is_enabled():
            return self._disabled_result()
        try:
            client = self._get_client()
            client.list_projects()
            return HealthResult(
                kind=self.kind,
                status=HealthStatus.HEALTHY,
                message="Connected to Jira",
            )
        except Exception as exc:
            return HealthResult(
                kind=self.kind,
                status=HealthStatus.UNHEALTHY,
                message=str(exc),
            )
