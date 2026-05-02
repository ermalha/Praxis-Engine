"""Session repository — CRUD for conversation sessions."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from praxis.errors import StorageError
from praxis.storage.db import get_connection
from praxis.storage.models import Session


class SessionRepo:
    """CRUD operations for the ``sessions`` table."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @property
    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    def create(self, session: Session) -> Session:
        """Insert a new session."""
        try:
            self._conn.execute(
                "INSERT INTO sessions (id, parent_id, profile, started_at, ended_at, "
                "summary, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    session.id,
                    session.parent_id,
                    session.profile,
                    session.started_at.isoformat(),
                    session.ended_at.isoformat() if session.ended_at else None,
                    session.summary,
                    json.dumps(session.metadata, default=str),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"Session already exists: {session.id}", id=session.id) from exc
        return session

    def get(self, session_id: str) -> Session | None:
        """Fetch a session by ID, or ``None`` if not found."""
        row = self._conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def list(self, *, limit: int = 50, offset: int = 0) -> list[Session]:
        """List sessions ordered by start time descending."""
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def update(self, session: Session) -> Session:
        """Update an existing session."""
        self._conn.execute(
            "UPDATE sessions SET parent_id=?, profile=?, started_at=?, ended_at=?, "
            "summary=?, metadata_json=? WHERE id=?",
            (
                session.parent_id,
                session.profile,
                session.started_at.isoformat(),
                session.ended_at.isoformat() if session.ended_at else None,
                session.summary,
                json.dumps(session.metadata, default=str),
                session.id,
            ),
        )
        self._conn.commit()
        return session

    def delete(self, session_id: str) -> bool:
        """Delete a session. Returns ``True`` if it existed."""
        cursor = self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            parent_id=row["parent_id"],
            profile=row["profile"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            summary=row["summary"],
            metadata=json.loads(row["metadata_json"]),
        )
