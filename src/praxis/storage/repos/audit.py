"""Audit repository — SQLite mirror of audit events."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from praxis.errors import StorageError
from praxis.storage.db import get_connection


class AuditRow:
    """Lightweight audit record from SQLite (not the full AuditEvent model)."""

    __slots__ = (
        "id",
        "timestamp",
        "profile",
        "engagement",
        "actor",
        "component",
        "event_type",
        "subject_id",
        "correlation_id",
        "payload",
    )

    def __init__(
        self,
        *,
        id: str,  # noqa: A002
        timestamp: str,
        profile: str,
        engagement: str | None,
        actor: str,
        component: str,
        event_type: str,
        subject_id: str | None,
        correlation_id: str | None,
        payload: dict[str, object],
    ) -> None:
        self.id = id
        self.timestamp = timestamp
        self.profile = profile
        self.engagement = engagement
        self.actor = actor
        self.component = component
        self.event_type = event_type
        self.subject_id = subject_id
        self.correlation_id = correlation_id
        self.payload = payload


class AuditRepo:
    """CRUD operations for the ``audit`` SQLite table."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @property
    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    def insert(
        self,
        *,
        event_id: str,
        timestamp: str,
        profile: str,
        engagement: str | None,
        actor: str,
        component: str,
        event_type: str,
        subject_id: str | None,
        correlation_id: str | None,
        payload: dict[str, object],
    ) -> None:
        """Insert an audit event into SQLite."""
        try:
            self._conn.execute(
                "INSERT INTO audit (id, timestamp, profile, engagement, actor, component, "
                "event_type, subject_id, correlation_id, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    timestamp,
                    profile,
                    engagement,
                    actor,
                    component,
                    event_type,
                    subject_id,
                    correlation_id,
                    json.dumps(payload, default=str),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"Audit event already exists: {event_id}") from exc

    def list(
        self,
        *,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditRow]:
        """Query audit events from SQLite."""
        conditions: list[str] = []
        params: list[object] = []

        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since.isoformat())

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        rows = self._conn.execute(
            f"SELECT * FROM audit{where} ORDER BY timestamp DESC LIMIT ?",  # noqa: S608
            params,
        ).fetchall()
        return [self._row_to_audit(r) for r in rows]

    @staticmethod
    def _row_to_audit(row: sqlite3.Row) -> AuditRow:
        return AuditRow(
            id=row["id"],
            timestamp=row["timestamp"],
            profile=row["profile"],
            engagement=row["engagement"],
            actor=row["actor"],
            component=row["component"],
            event_type=row["event_type"],
            subject_id=row["subject_id"],
            correlation_id=row["correlation_id"],
            payload=json.loads(row["payload_json"]),
        )
