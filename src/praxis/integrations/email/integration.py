"""Email integration — IMAP + SMTP connectors."""

from __future__ import annotations

from praxis.config.models import IntegrationConfig
from praxis.integrations.base import Integration
from praxis.integrations.models import HealthResult, HealthStatus
from praxis.integrations.registry import register_integration


@register_integration
class ImapIntegration(Integration):
    """IMAP inbox watcher integration."""

    name = "IMAP Inbox"
    kind = "imap"

    def health_check(self) -> HealthResult:
        if not self.is_enabled():
            return self._disabled_result()
        try:
            from praxis.integrations.email.imap_watcher import ImapWatcher

            watcher = ImapWatcher(self.settings)
            if watcher.check_connectivity():
                return HealthResult(
                    kind=self.kind,
                    status=HealthStatus.HEALTHY,
                    message="Connected to IMAP server",
                )
            return HealthResult(
                kind=self.kind,
                status=HealthStatus.UNHEALTHY,
                message="IMAP connectivity check failed",
            )
        except Exception as exc:
            return HealthResult(
                kind=self.kind,
                status=HealthStatus.UNHEALTHY,
                message=str(exc),
            )


@register_integration
class SmtpIntegration(Integration):
    """SMTP email sender integration."""

    name = "SMTP Sender"
    kind = "smtp"

    def __init__(self, config: IntegrationConfig) -> None:
        super().__init__(config)

    def health_check(self) -> HealthResult:
        if not self.is_enabled():
            return self._disabled_result()
        try:
            from praxis.integrations.email.smtp_sender import SmtpSender

            sender = SmtpSender(self.settings)
            if sender.check_connectivity():
                return HealthResult(
                    kind=self.kind,
                    status=HealthStatus.HEALTHY,
                    message="Connected to SMTP server",
                )
            return HealthResult(
                kind=self.kind,
                status=HealthStatus.UNHEALTHY,
                message="SMTP connectivity check failed",
            )
        except Exception as exc:
            return HealthResult(
                kind=self.kind,
                status=HealthStatus.UNHEALTHY,
                message=str(exc),
            )
