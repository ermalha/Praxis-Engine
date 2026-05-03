"""Webhook receiver — lightweight HTTP endpoint for external events."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import structlog

from praxis.audit import emit
from praxis.errors import IntegrationError

logger = structlog.get_logger()


class WebhookReceiver:
    """Receives and validates webhook payloads.

    Each registered path has a secret token for HMAC validation and a
    handler kind that determines how the payload is processed.
    """

    def __init__(self, settings: dict[str, str], engagement_path: Path) -> None:
        self._engagement_path = engagement_path
        self._port = int(settings.get("port", "8765"))
        self._paths = self._parse_paths(settings)

    @property
    def port(self) -> int:
        return self._port

    @property
    def paths(self) -> list[dict[str, str]]:
        return self._paths

    def validate_and_persist(
        self,
        path: str,
        payload: bytes,
        signature: str | None = None,
    ) -> Path:
        """Validate a webhook request and persist the payload.

        Returns the path to the persisted JSON file.
        """
        path_config = self._find_path(path)
        if path_config is None:
            raise IntegrationError(
                f"No webhook registered for path: {path}",
                kind="webhook",
            )

        secret_env = path_config.get("secret_env", "")
        if secret_env:
            secret = os.environ.get(secret_env, "")
            if secret and signature and not self._verify_signature(payload, secret, signature):
                raise IntegrationError(
                    "Webhook signature verification failed",
                    kind="webhook",
                    path=path,
                )

        inbox_dir = self._engagement_path / ".praxis" / "state" / "inbox" / "webhook"
        inbox_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{ts}.json"
        dest = inbox_dir / filename

        try:
            parsed = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            parsed = {"raw": payload.decode("utf-8", errors="replace")}

        dest.write_text(
            json.dumps(
                {
                    "received_at": datetime.now(UTC).isoformat(),
                    "path": path,
                    "kind": path_config.get("kind", "unknown"),
                    "payload": parsed,
                },
                indent=2,
            )
        )

        emit(
            "inbox.webhook_received",
            path=path,
            kind=path_config.get("kind", "unknown"),
            file=str(dest),
        )

        logger.info("webhook.received", path=path, file=str(dest))
        return dest

    def _find_path(self, path: str) -> dict[str, str] | None:
        for p in self._paths:
            if p.get("path") == path:
                return p
        return None

    def _verify_signature(
        self,
        payload: bytes,
        secret: str,
        signature: str,
    ) -> bool:
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        sig_value = signature.removeprefix("sha256=")
        return hmac.compare_digest(expected, sig_value)

    @staticmethod
    def _parse_paths(settings: dict[str, str]) -> list[dict[str, str]]:
        """Parse path configs from settings.

        Settings may contain paths as a JSON string or as indexed keys.
        """
        paths_raw = settings.get("paths", "[]")
        if paths_raw.startswith("["):
            try:
                return json.loads(paths_raw)
            except (json.JSONDecodeError, ValueError):
                return []
        return []
