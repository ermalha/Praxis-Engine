"""Webhook integration registration."""

from __future__ import annotations

from praxis.integrations.base import Integration
from praxis.integrations.models import HealthResult, HealthStatus
from praxis.integrations.registry import register_integration


@register_integration
class WebhookIntegration(Integration):
    """Generic webhook receiver integration."""

    name = "Webhook Receiver"
    kind = "webhook"

    def health_check(self) -> HealthResult:
        if not self.is_enabled():
            return self._disabled_result()
        return HealthResult(
            kind=self.kind,
            status=HealthStatus.HEALTHY,
            message=f"Webhook receiver configured on port {self.settings.get('port', '8765')}",
        )
