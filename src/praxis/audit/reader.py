"""Audit log reader — tail and query operations."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from praxis.audit.models import AuditEvent
from praxis.errors import AuditError


def tail(
    path: Path,
    *,
    n: int = 100,
) -> list[AuditEvent]:
    """Read the last *n* events from a JSONL audit file.

    Args:
        path: Path to the audit JSONL file.
        n: Number of events to return (from the end).

    Returns:
        List of :class:`AuditEvent`, most recent last.
    """
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-n:] if len(lines) > n else lines
    events: list[AuditEvent] = []
    for line in recent:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            events.append(AuditEvent.model_validate(data))
        except Exception as exc:
            raise AuditError(f"Failed to parse audit line: {exc}", line=line) from exc
    return events


def query(
    path: Path,
    *,
    event_type: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[AuditEvent]:
    """Query a JSONL audit file with optional filters.

    Args:
        path: Path to the audit JSONL file.
        event_type: Filter by event type (exact match).
        since: Only include events at or after this timestamp.
        limit: Maximum results.

    Returns:
        Matching events, most recent first.
    """
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    events: list[AuditEvent] = []

    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            event = AuditEvent.model_validate(data)
        except Exception:
            continue

        if event_type is not None and event.event_type != event_type:
            continue
        if since is not None and event.timestamp < since:
            continue

        events.append(event)
        if len(events) >= limit:
            break

    return events
