"""IMAP inbox watcher — fetches new messages since last check."""

from __future__ import annotations

import email
import imaplib
import os
import ssl
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from praxis.errors import IntegrationError
from praxis.integrations.email.models import ParsedMessage

logger = structlog.get_logger()


class ImapWatcher:
    """Watches an IMAP mailbox for new messages."""

    def __init__(self, settings: dict[str, str]) -> None:
        self._host = settings.get("host", "")
        self._port = int(settings.get("port", "993"))
        self._tls = settings.get("tls", "true").lower() == "true"
        self._mailbox = settings.get("mailbox", "INBOX")

        user_env = settings.get("user_env", "PRAXIS_IMAP_USER")
        password_env = settings.get("password_env", "PRAXIS_IMAP_PASSWORD")
        self._user = os.environ.get(user_env, "")
        self._password = os.environ.get(password_env, "")

        if not self._host:
            raise IntegrationError("IMAP host not configured", kind="imap")
        if not self._user or not self._password:
            raise IntegrationError(
                f"IMAP credentials missing: set {user_env} and {password_env}",
                kind="imap",
            )

    def fetch_since(
        self,
        since: datetime | None = None,
        state_dir: Path | None = None,
    ) -> list[ParsedMessage]:
        """Fetch messages since the given date (or last-check marker)."""
        if since is None and state_dir is not None:
            since = self._read_last_check(state_dir)

        conn = self._connect()
        try:
            conn.select(self._mailbox, readonly=True)
            criteria = "ALL"
            if since:
                date_str = since.strftime("%d-%b-%Y")
                criteria = f"(SINCE {date_str})"
            _, data = conn.search(None, criteria)
            msg_nums = data[0].split() if data[0] else []

            messages: list[ParsedMessage] = []
            for num in msg_nums:
                _, msg_data = conn.fetch(num, "(RFC822)")
                if msg_data and msg_data[0] is not None:
                    raw: Any = msg_data[0]
                    if isinstance(raw, tuple) and len(raw) >= 2:
                        parsed = self._parse_message(raw[1])
                        if parsed:
                            messages.append(parsed)

            if state_dir is not None:
                self._write_last_check(state_dir)

            return messages
        finally:
            conn.logout()

    def check_connectivity(self) -> bool:
        """Test if we can connect to the IMAP server."""
        try:
            conn = self._connect()
            conn.logout()
            return True
        except Exception:
            return False

    def _connect(self) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        if self._tls:
            ctx = ssl.create_default_context()
            conn = imaplib.IMAP4_SSL(self._host, self._port, ssl_context=ctx)
        else:
            conn = imaplib.IMAP4(self._host, self._port)
        conn.login(self._user, self._password)
        return conn

    def _parse_message(self, raw_bytes: bytes) -> ParsedMessage | None:
        """Parse a raw RFC822 message into our model."""
        try:
            msg = email.message_from_bytes(raw_bytes)
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")

            date_str = msg.get("Date", "")
            date = None
            if date_str:
                parsed = email.utils.parsedate_to_datetime(date_str)
                date = parsed.astimezone(UTC)

            to_raw = msg.get("To", "")
            to_addrs = [a.strip() for a in to_raw.split(",") if a.strip()]

            return ParsedMessage(
                message_id=msg.get("Message-ID", ""),
                in_reply_to=msg.get("In-Reply-To"),
                from_addr=msg.get("From", ""),
                to_addrs=to_addrs,
                subject=msg.get("Subject", ""),
                body=body,
                date=date,
            )
        except Exception:
            logger.warning("imap.parse_failed", exc_info=True)
            return None

    def _read_last_check(self, state_dir: Path) -> datetime | None:
        marker = state_dir / "imap_last_check"
        if marker.exists():
            ts = marker.read_text().strip()
            if ts:
                return datetime.fromisoformat(ts)
        return None

    def _write_last_check(self, state_dir: Path) -> None:
        marker = state_dir / "imap_last_check"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(datetime.now(UTC).isoformat())
