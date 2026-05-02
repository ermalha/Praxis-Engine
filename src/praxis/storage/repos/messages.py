"""Message repository — CRUD + FTS5 search for conversation messages."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from praxis.errors import StorageError
from praxis.storage.db import get_connection
from praxis.storage.models import FTSResult, Message, MessageRole


class MessageRepo:
    """CRUD operations and full-text search for the ``messages`` table."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @property
    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    def create(self, message: Message) -> Message:
        """Insert a new message."""
        try:
            self._conn.execute(
                "INSERT INTO messages (id, session_id, turn, role, content, "
                "tool_calls_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    message.id,
                    message.session_id,
                    message.turn,
                    message.role.value,
                    message.content,
                    message.tool_calls_json,
                    message.created_at.isoformat(),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise StorageError(
                f"Message conflict: {exc}", id=message.id, session_id=message.session_id
            ) from exc
        return message

    def get(self, message_id: str) -> Message | None:
        """Fetch a message by ID."""
        row = self._conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_message(row)

    def list_by_session(self, session_id: str) -> list[Message]:
        """List messages for a session, ordered by turn."""
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY turn",
            (session_id,),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def delete(self, message_id: str) -> bool:
        """Delete a message. Returns ``True`` if it existed."""
        cursor = self._conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def fts_search(self, query: str, *, limit: int = 20) -> list[FTSResult]:
        """Full-text search across message content.

        Args:
            query: FTS5 query string.
            limit: Maximum results.
        """
        rows = self._conn.execute(
            "SELECT m.id AS message_id, m.session_id, m.role, m.content, "
            "f.rank AS rank "
            "FROM messages_fts f "
            "JOIN messages m ON m.rowid = f.rowid "
            "WHERE messages_fts MATCH ? "
            "ORDER BY f.rank LIMIT ?",
            (query, limit),
        ).fetchall()
        return [
            FTSResult(
                message_id=r["message_id"],
                session_id=r["session_id"],
                role=r["role"],
                content=r["content"],
                rank=float(r["rank"]),
            )
            for r in rows
        ]

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> Message:
        return Message(
            id=row["id"],
            session_id=row["session_id"],
            turn=row["turn"],
            role=MessageRole(row["role"]),
            content=row["content"],
            tool_calls_json=row["tool_calls_json"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
