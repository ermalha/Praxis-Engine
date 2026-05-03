"""SMTP email sender."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

import structlog

from praxis.errors import IntegrationError

logger = structlog.get_logger()


class SmtpSender:
    """Sends email via SMTP."""

    def __init__(self, settings: dict[str, str]) -> None:
        self._host = settings.get("host", "")
        self._port = int(settings.get("port", "587"))
        self._tls = settings.get("tls", "true").lower() == "true"

        user_env = settings.get("user_env", "PRAXIS_SMTP_USER")
        password_env = settings.get("password_env", "PRAXIS_SMTP_PASSWORD")
        self._user = os.environ.get(user_env, "")
        self._password = os.environ.get(password_env, "")
        self._from_addr = settings.get("from_addr", self._user)

        if not self._host:
            raise IntegrationError("SMTP host not configured", kind="smtp")
        if not self._user or not self._password:
            raise IntegrationError(
                f"SMTP credentials missing: set {user_env} and {password_env}",
                kind="smtp",
            )

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        *,
        cc: str | None = None,
        in_reply_to: str | None = None,
    ) -> None:
        """Send an email message."""
        msg = EmailMessage()
        msg["From"] = self._from_addr
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to
        msg.set_content(body)

        if self._tls:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(self._host, self._port) as server:
                server.starttls(context=ctx)
                server.login(self._user, self._password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(self._host, self._port) as server:
                server.login(self._user, self._password)
                server.send_message(msg)

        logger.info("smtp.sent", to=to, subject=subject)

    def check_connectivity(self) -> bool:
        """Test SMTP connectivity."""
        try:
            with smtplib.SMTP(self._host, self._port) as server:
                if self._tls:
                    ctx = ssl.create_default_context()
                    server.starttls(context=ctx)
                server.login(self._user, self._password)
            return True
        except Exception:
            return False
