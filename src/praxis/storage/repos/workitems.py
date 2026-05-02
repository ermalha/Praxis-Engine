"""Work-item repository — CRUD for the work queue."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from praxis.errors import StorageError
from praxis.storage.db import get_connection
from praxis.storage.models import WorkItem, WorkItemPriority, WorkItemStatus


class WorkItemRepo:
    """CRUD operations for the ``workitems`` table."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @property
    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    def create(self, item: WorkItem) -> WorkItem:
        """Insert a new work-item."""
        try:
            self._conn.execute(
                "INSERT INTO workitems (id, type, status, priority, payload_json, "
                "created_at, updated_at, deadline, completed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.id,
                    item.type,
                    item.status.value,
                    item.priority.value,
                    json.dumps(item.payload, default=str),
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                    item.deadline.isoformat() if item.deadline else None,
                    item.completed_at.isoformat() if item.completed_at else None,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise StorageError(f"Work-item already exists: {item.id}", id=item.id) from exc
        return item

    def get(self, item_id: str) -> WorkItem | None:
        """Fetch a work-item by ID."""
        row = self._conn.execute("SELECT * FROM workitems WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_workitem(row)

    def list(
        self,
        *,
        status: WorkItemStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkItem]:
        """List work-items, optionally filtered by status."""
        if status is not None:
            rows = self._conn.execute(
                "SELECT * FROM workitems WHERE status = ? "
                "ORDER BY priority, created_at LIMIT ? OFFSET ?",
                (status.value, limit, offset),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM workitems ORDER BY status, priority, created_at LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_workitem(r) for r in rows]

    def update(self, item: WorkItem) -> WorkItem:
        """Update an existing work-item."""
        self._conn.execute(
            "UPDATE workitems SET type=?, status=?, priority=?, payload_json=?, "
            "updated_at=?, deadline=?, completed_at=? WHERE id=?",
            (
                item.type,
                item.status.value,
                item.priority.value,
                json.dumps(item.payload, default=str),
                item.updated_at.isoformat(),
                item.deadline.isoformat() if item.deadline else None,
                item.completed_at.isoformat() if item.completed_at else None,
                item.id,
            ),
        )
        self._conn.commit()
        return item

    def delete(self, item_id: str) -> bool:
        """Delete a work-item. Returns ``True`` if it existed."""
        cursor = self._conn.execute("DELETE FROM workitems WHERE id = ?", (item_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_workitem(row: sqlite3.Row) -> WorkItem:
        return WorkItem(
            id=row["id"],
            type=row["type"],
            status=WorkItemStatus(row["status"]),
            priority=WorkItemPriority(row["priority"]),
            payload=json.loads(row["payload_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deadline=datetime.fromisoformat(row["deadline"]) if row["deadline"] else None,
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
        )
