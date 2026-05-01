"""Praxis audit subsystem.

Stub implementation for chunk 02. Writes JSONL audit events to disk.
Full structured audit subsystem arrives in chunk 03.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog

logger = structlog.get_logger(component="audit")

_DEFAULT_HOME = Path.home() / ".praxis"


def emit(
    event_type: str,
    *,
    profile: str = "default",
    engagement: str | None = None,
    engagement_path: Path | None = None,
    actor: str = "system",
    subject_id: str | None = None,
    correlation_id: str | None = None,
    **payload: object,
) -> None:
    """Write a single audit event as a JSONL line.

    Writes to both the global audit log (``~/.praxis/audit.jsonl``) and,
    if *engagement_path* is provided, the engagement-local audit log.

    Args:
        event_type: Dotted event name, e.g. ``"profile.created"``.
        profile: Active profile name.
        engagement: Engagement name (human-readable).
        engagement_path: Path to the engagement root (contains ``.praxis/``).
        actor: One of ``"agent"``, ``"human"``, ``"system"``.
        subject_id: ID of the affected entity.
        correlation_id: For tracing related events.
        **payload: Arbitrary event-specific data.
    """
    event = {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "profile": profile,
        "engagement": engagement,
        "actor": actor,
        "component": "audit",
        "event_type": event_type,
        "subject_id": subject_id,
        "payload": payload,
        "correlation_id": correlation_id,
    }

    line = json.dumps(event, default=str) + "\n"

    # Global audit log
    home = Path(os.environ.get("PRAXIS_HOME", str(_DEFAULT_HOME)))
    home.mkdir(parents=True, exist_ok=True)
    global_log = home / "audit.jsonl"
    with open(global_log, "a") as f:
        f.write(line)

    # Per-engagement audit log
    if engagement_path is not None:
        state_dir = engagement_path / ".praxis" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        eng_log = state_dir / "audit.jsonl"
        with open(eng_log, "a") as f:
            f.write(line)

    logger.debug("audit.emitted", event_type=event_type, event_id=event["event_id"])
