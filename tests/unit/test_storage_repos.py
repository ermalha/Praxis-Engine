"""Tests for storage repository classes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from praxis.errors import StorageError
from praxis.storage import (
    Message,
    MessageRepo,
    MessageRole,
    Session,
    SessionRepo,
    WorkItem,
    WorkItemPriority,
    WorkItemRepo,
    WorkItemStatus,
)
from praxis.storage.repos import AuditRepo


def _now() -> datetime:
    return datetime.now(UTC)


class TestSessionRepo:
    def test_create_and_get(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        repo = SessionRepo(db)
        sess = Session(id=str(uuid.uuid4()), profile="default", started_at=_now())
        repo.create(sess)
        loaded = repo.get(sess.id)
        assert loaded is not None
        assert loaded.id == sess.id
        assert loaded.profile == "default"

    def test_list_sessions(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        repo = SessionRepo(db)
        for _ in range(3):
            repo.create(Session(id=str(uuid.uuid4()), profile="default", started_at=_now()))
        sessions = repo.list(limit=10)
        assert len(sessions) == 3

    def test_update_session(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        repo = SessionRepo(db)
        sess = Session(id=str(uuid.uuid4()), profile="default", started_at=_now())
        repo.create(sess)
        sess.summary = "Updated summary"
        sess.ended_at = _now()
        repo.update(sess)
        loaded = repo.get(sess.id)
        assert loaded is not None
        assert loaded.summary == "Updated summary"
        assert loaded.ended_at is not None

    def test_delete_session(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        repo = SessionRepo(db)
        sess = Session(id=str(uuid.uuid4()), profile="default", started_at=_now())
        repo.create(sess)
        assert repo.delete(sess.id) is True
        assert repo.get(sess.id) is None

    def test_duplicate_raises(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        repo = SessionRepo(db)
        sess = Session(id="dup-id", profile="default", started_at=_now())
        repo.create(sess)
        with pytest.raises(StorageError, match="already exists"):
            repo.create(sess)


class TestMessageRepo:
    def _create_session(self, db: Path) -> str:
        repo = SessionRepo(db)
        sid = str(uuid.uuid4())
        repo.create(Session(id=sid, profile="default", started_at=_now()))
        return sid

    def test_create_and_list(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        sid = self._create_session(db)
        repo = MessageRepo(db)
        msg = Message(
            id=str(uuid.uuid4()),
            session_id=sid,
            turn=1,
            role=MessageRole.USER,
            content="hello world",
            created_at=_now(),
        )
        repo.create(msg)
        msgs = repo.list_by_session(sid)
        assert len(msgs) == 1
        assert msgs[0].content == "hello world"

    def test_fts_search(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        sid = self._create_session(db)
        repo = MessageRepo(db)
        repo.create(
            Message(
                id=str(uuid.uuid4()),
                session_id=sid,
                turn=1,
                role=MessageRole.USER,
                content="the quick brown fox jumps",
                created_at=_now(),
            )
        )
        repo.create(
            Message(
                id=str(uuid.uuid4()),
                session_id=sid,
                turn=2,
                role=MessageRole.ASSISTANT,
                content="hello there",
                created_at=_now(),
            )
        )
        hits = repo.fts_search("quick brown")
        assert len(hits) == 1
        assert "fox" in hits[0].content

    def test_delete_message(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        sid = self._create_session(db)
        repo = MessageRepo(db)
        mid = str(uuid.uuid4())
        repo.create(
            Message(
                id=mid,
                session_id=sid,
                turn=1,
                role=MessageRole.USER,
                content="test",
                created_at=_now(),
            )
        )
        assert repo.delete(mid) is True
        assert repo.get(mid) is None


class TestWorkItemRepo:
    def test_create_and_get(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        repo = WorkItemRepo(db)
        now = _now()
        item = WorkItem(
            id=str(uuid.uuid4()),
            type="question",
            status=WorkItemStatus.PENDING,
            priority=WorkItemPriority.HIGH,
            payload={"text": "What is X?"},
            created_at=now,
            updated_at=now,
        )
        repo.create(item)
        loaded = repo.get(item.id)
        assert loaded is not None
        assert loaded.payload == {"text": "What is X?"}

    def test_list_by_status(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        repo = WorkItemRepo(db)
        now = _now()
        for i, status in enumerate([WorkItemStatus.PENDING, WorkItemStatus.COMPLETED]):
            repo.create(
                WorkItem(
                    id=str(uuid.uuid4()),
                    type="task",
                    status=status,
                    priority=WorkItemPriority.MEDIUM,
                    payload={},
                    created_at=now,
                    updated_at=now,
                )
            )
        pending = repo.list(status=WorkItemStatus.PENDING)
        assert len(pending) == 1

    def test_update_workitem(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        repo = WorkItemRepo(db)
        now = _now()
        item = WorkItem(
            id=str(uuid.uuid4()),
            type="task",
            status=WorkItemStatus.PENDING,
            priority=WorkItemPriority.LOW,
            payload={},
            created_at=now,
            updated_at=now,
        )
        repo.create(item)
        item.status = WorkItemStatus.COMPLETED
        item.completed_at = _now()
        repo.update(item)
        loaded = repo.get(item.id)
        assert loaded is not None
        assert loaded.status == WorkItemStatus.COMPLETED


class TestAuditRepo:
    def test_insert_and_list(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        repo = AuditRepo(db)
        # db_engagement fixture already emits engagement.initialized
        before_count = len(repo.list(limit=100))
        repo.insert(
            event_id=str(uuid.uuid4()),
            timestamp=_now().isoformat(),
            profile="default",
            engagement="test",
            actor="system",
            component="test",
            event_type="test.event",
            subject_id="s1",
            correlation_id=None,
            payload={"key": "value"},
        )
        rows = repo.list(limit=100)
        assert len(rows) == before_count + 1
        assert any(r.event_type == "test.event" for r in rows)

    def test_list_filter_by_type(self, db_engagement: Path) -> None:
        db = db_engagement / ".praxis" / "state" / "praxis.db"
        repo = AuditRepo(db)
        for etype in ["a.one", "b.two", "a.one"]:
            repo.insert(
                event_id=str(uuid.uuid4()),
                timestamp=_now().isoformat(),
                profile="default",
                engagement=None,
                actor="system",
                component="test",
                event_type=etype,
                subject_id=None,
                correlation_id=None,
                payload={},
            )
        rows = repo.list(event_type="a.one")
        assert len(rows) == 2
