"""Work-queue repository — persistence with state machine enforcement."""

from __future__ import annotations

import builtins
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from praxis.audit import emit
from praxis.errors import WorkqueueError
from praxis.storage.db import get_connection

from .models import (
    WorkItem,
    WorkItemPriority,
    WorkItemStatus,
    WorkItemType,
    is_valid_transition,
)

_ID_PREFIX = "wi-"


def _generate_id() -> str:
    import uuid

    return _ID_PREFIX + uuid.uuid4().hex[:10]


class WorkQueueRepo:
    """Rich work-queue operations with state machine enforcement."""

    def __init__(self, engagement_path: Path) -> None:
        self._engagement_path = engagement_path
        self._db_path = engagement_path / ".praxis" / "state" / "praxis.db"
        self._jsonl_path = engagement_path / ".praxis" / "state" / "workqueue.jsonl"

    @property
    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    def create(self, item: WorkItem) -> WorkItem:
        """Insert a new work-item."""
        payload = item.model_dump(mode="json")
        try:
            self._conn.execute(
                "INSERT INTO workitems (id, type, status, priority, payload_json, "
                "created_at, updated_at, deadline, completed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.id,
                    item.type.value,
                    item.status.value,
                    item.priority.value,
                    json.dumps(payload, default=str),
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                    item.deadline.isoformat() if item.deadline else None,
                    item.completed_at.isoformat() if item.completed_at else None,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise WorkqueueError(f"Work-item already exists: {item.id}", id=item.id) from exc

        # Append to JSONL
        self._append_jsonl({"action": "created", **payload})

        emit(
            "workitem.created",
            component="workqueue",
            subject_id=item.id,
            engagement_path=self._engagement_path,
            item_type=item.type.value,
            assignee=item.assignee,
            priority=item.priority.value,
        )

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
        assignee: str | None = None,
        priority: WorkItemPriority | None = None,
        limit: int = 50,
    ) -> list[WorkItem]:
        """List work-items with optional filters."""
        query = "SELECT * FROM workitems WHERE 1=1"
        params: list[object] = []

        if status is not None:
            query += " AND status = ?"
            params.append(status.value)

        if priority is not None:
            query += " AND priority = ?"
            params.append(priority.value)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        items = [self._row_to_workitem(r) for r in rows]

        # Filter by assignee in Python (stored in payload_json)
        if assignee is not None:
            items = [i for i in items if i.assignee == assignee]

        return items

    def transition(
        self,
        item_id: str,
        to: WorkItemStatus,
        *,
        note: str | None = None,
        return_payload: dict[str, object] | None = None,
    ) -> WorkItem:
        """Transition a work-item to a new status with validation."""
        item = self.get(item_id)
        if item is None:
            raise WorkqueueError(f"Work-item not found: {item_id}", id=item_id)

        if not is_valid_transition(item.status, to):
            raise WorkqueueError(
                f"Invalid transition: {item.status.value} → {to.value}",
                id=item_id,
                from_status=item.status.value,
                to_status=to.value,
            )

        now = datetime.now(UTC)
        updates: dict[str, object] = {
            "status": to,
            "updated_at": now,
        }

        if note is not None:
            updates["completion_note"] = note

        if return_payload is not None:
            updates["return_payload"] = return_payload

        if to == WorkItemStatus.DONE:
            updates["completed_at"] = now

        updated = item.model_copy(update=updates)
        self._save(updated)

        # Append to JSONL
        self._append_jsonl(
            {
                "action": "transitioned",
                "id": item_id,
                "from": item.status.value,
                "to": to.value,
                "note": note,
            }
        )

        # Emit specific audit events
        event_map = {
            WorkItemStatus.DONE: "workitem.committed",
            WorkItemStatus.REJECTED: "workitem.rejected",
            WorkItemStatus.DEFERRED: "workitem.deferred",
        }
        event_type = event_map.get(to, "workitem.transitioned")
        emit(
            event_type,
            component="workqueue",
            subject_id=item_id,
            engagement_path=self._engagement_path,
            from_status=item.status.value,
            to_status=to.value,
            note=note,
        )

        return updated

    def update(self, item_id: str, **fields: object) -> WorkItem:
        """Update fields on a work-item (no status change)."""
        item = self.get(item_id)
        if item is None:
            raise WorkqueueError(f"Work-item not found: {item_id}", id=item_id)

        fields["updated_at"] = datetime.now(UTC)
        updated = item.model_copy(update=fields)
        self._save(updated)
        return updated

    def enqueue(
        self,
        *,
        type: WorkItemType,  # noqa: A002
        assignee: str,
        title: str,
        description: str,
        priority: WorkItemPriority = WorkItemPriority.MEDIUM,
        payload: dict[str, object] | None = None,
        rationale: str = "",
        related_question_ids: builtins.list[str] | None = None,
        related_stakeholder_ids: builtins.list[str] | None = None,
        deadline: datetime | None = None,
    ) -> WorkItem:
        """Create and enqueue a new work-item (convenience method)."""
        now = datetime.now(UTC)
        item = WorkItem(
            id=_generate_id(),
            type=WorkItemType(type),
            assignee=assignee,  # type: ignore[arg-type]
            status=WorkItemStatus.QUEUED,
            priority=priority,
            title=title,
            description=description,
            payload=payload or {},
            rationale=rationale,
            related_question_ids=related_question_ids or [],
            related_stakeholder_ids=related_stakeholder_ids or [],
            deadline=deadline,
            created_at=now,
            updated_at=now,
        )
        return self.create(item)

    def _save(self, item: WorkItem) -> None:
        """Save (update) an existing work-item."""
        payload = item.model_dump(mode="json")
        self._conn.execute(
            "UPDATE workitems SET type=?, status=?, priority=?, payload_json=?, "
            "updated_at=?, deadline=?, completed_at=? WHERE id=?",
            (
                item.type.value,
                item.status.value,
                item.priority.value,
                json.dumps(payload, default=str),
                item.updated_at.isoformat(),
                item.deadline.isoformat() if item.deadline else None,
                item.completed_at.isoformat() if item.completed_at else None,
                item.id,
            ),
        )
        self._conn.commit()

    def _append_jsonl(self, data: dict[str, object]) -> None:
        """Append an entry to the JSONL log."""
        self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, default=str) + "\n")

    @staticmethod
    def _row_to_workitem(row: sqlite3.Row) -> WorkItem:
        """Reconstruct a WorkItem from the rich payload_json."""
        payload_data = json.loads(row["payload_json"])
        # The full WorkItem is stored in payload_json
        if "schema_version" in payload_data:
            return WorkItem.model_validate(payload_data)
        # Fallback for legacy rows without full payload
        return WorkItem(
            id=row["id"],
            type=row["type"],
            assignee="human",
            status=WorkItemStatus(row["status"]),
            priority=WorkItemPriority(row["priority"]),
            title=row["id"],
            description="",
            payload=payload_data,
            rationale="",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deadline=(datetime.fromisoformat(row["deadline"]) if row["deadline"] else None),
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
        )
