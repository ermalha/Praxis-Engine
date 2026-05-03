"""Webhook HTTP server — uses FastAPI when available."""

from __future__ import annotations

from pathlib import Path

import structlog

from praxis.errors import IntegrationError

logger = structlog.get_logger()


def create_app(settings: dict[str, str], engagement_path: Path):
    """Create the FastAPI app for webhook reception.

    Raises IntegrationError if fastapi is not installed.
    """
    try:
        from fastapi import FastAPI, Request, Response
    except ImportError:
        raise IntegrationError(
            "fastapi not installed. Install: pip install praxis-ba[webhook]",
            kind="webhook",
        ) from None

    from praxis.integrations.webhook.receiver import WebhookReceiver

    receiver = WebhookReceiver(settings, engagement_path)
    app = FastAPI(title="Praxis Webhook Receiver")

    @app.post("/{path:path}")
    async def receive_webhook(path: str, request: Request) -> Response:
        full_path = f"/{path}"
        payload = await request.body()
        signature = request.headers.get("X-Hub-Signature-256")
        try:
            dest = receiver.validate_and_persist(full_path, payload, signature)
            return Response(
                content=f'{{"status":"ok","file":"{dest.name}"}}',
                media_type="application/json",
                status_code=200,
            )
        except IntegrationError as exc:
            return Response(
                content=f'{{"error":"{exc}"}}',
                media_type="application/json",
                status_code=400,
            )

    return app


def serve(settings: dict[str, str], engagement_path: Path) -> None:
    """Run the webhook server (blocking)."""
    try:
        import uvicorn
    except ImportError:
        raise IntegrationError(
            "uvicorn not installed. Install: pip install praxis-ba[webhook]",
            kind="webhook",
        ) from None

    app = create_app(settings, engagement_path)
    port = int(settings.get("port", "8765"))
    logger.info("webhook.server_starting", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port)
