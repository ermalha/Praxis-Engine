"""Audit event writer.

Writes audit events to:
1. Global JSONL file (``~/.praxis/audit.jsonl``)
2. Per-engagement JSONL file (if engagement context is set)
3. Per-engagement SQLite ``audit`` table (if DB available)
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import structlog

from praxis.audit.context import get_audit_context
from praxis.audit.models import AuditEvent

logger = structlog.get_logger(component="audit")

_DEFAULT_HOME = Path.home() / ".praxis"


def emit(
    event_type: str,
    *,
    component: str = "audit",
    profile: str | None = None,
    engagement: str | None = None,
    engagement_path: Path | None = None,
    actor: Literal["agent", "human", "system"] = "system",
    subject_id: str | None = None,
    correlation_id: str | None = None,
    **payload: object,
) -> AuditEvent:
    """Emit a structured audit event.

    Resolves the current profile and engagement from the :mod:`context`
    ContextVar. Explicit *profile*, *engagement*, and *engagement_path*
    kwargs override the ContextVar values (useful for lifecycle functions
    that run outside orchestrator context).

    Args:
        event_type: Dotted event name, e.g. ``"profile.created"``.
        component: Subsystem emitting the event.
        profile: Override profile (defaults to context).
        engagement: Override engagement name (defaults to context).
        engagement_path: Override engagement path (defaults to context).
        actor: One of ``"agent"``, ``"human"``, ``"system"``.
        subject_id: ID of the affected entity.
        correlation_id: For tracing related events.
        **payload: Arbitrary event-specific data.

    Returns:
        The constructed :class:`AuditEvent`.
    """
    ctx = get_audit_context()
    resolved_profile = profile if profile is not None else ctx.profile
    resolved_engagement = engagement if engagement is not None else ctx.engagement
    resolved_path = engagement_path if engagement_path is not None else ctx.engagement_path

    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC),
        profile=resolved_profile,
        engagement=resolved_engagement,
        actor=actor,
        component=component,
        event_type=event_type,
        subject_id=subject_id,
        payload=dict(payload),
        correlation_id=correlation_id,
    )

    line = event.model_dump_json() + "\n"

    # Global audit log
    home = Path(os.environ.get("PRAXIS_HOME", str(_DEFAULT_HOME)))
    home.mkdir(parents=True, exist_ok=True)
    global_log = home / "audit.jsonl"
    with open(global_log, "a") as f:
        f.write(line)

    # Per-engagement audit log + SQLite mirror
    if resolved_path is not None:
        state_dir = resolved_path / ".praxis" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        eng_log = state_dir / "audit.jsonl"
        with open(eng_log, "a") as f:
            f.write(line)

        # Mirror to SQLite if DB exists
        db_path = state_dir / "praxis.db"
        if db_path.exists():
            _mirror_to_sqlite(db_path, event)

    logger.debug("audit.emitted", event_type=event_type, event_id=event.event_id)
    return event


def _mirror_to_sqlite(db_path: Path, event: AuditEvent) -> None:
    """Write an audit event to the SQLite audit table."""
    try:
        from praxis.storage.repos.audit import AuditRepo

        repo = AuditRepo(db_path)
        repo.insert(
            event_id=event.event_id,
            timestamp=event.timestamp.isoformat(),
            profile=event.profile,
            engagement=event.engagement,
            actor=event.actor,
            component=event.component,
            event_type=event.event_type,
            subject_id=event.subject_id,
            correlation_id=event.correlation_id,
            payload=event.payload,
        )
    except Exception:
        # Don't let SQLite mirror failures break the primary audit path
        logger.warning(
            "audit.sqlite_mirror_failed",
            event_id=event.event_id,
            db_path=str(db_path),
        )
