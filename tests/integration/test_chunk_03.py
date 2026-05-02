"""Chunk 03 acceptance test — storage layer end-to-end."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from praxis.audit import AuditEvent, emit, set_audit_context, tail
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
    read_yaml_typed,
    write_yaml_typed,
)
from praxis.storage.repos import AuditRepo


def _now() -> datetime:
    return datetime.now(UTC)


class Glossary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    terms: list[Term] = []


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")
    term: str
    definition: str


# Rebuild Glossary to pick up the Term forward ref
Glossary.model_rebuild()


def test_storage_end_to_end(db_engagement: Path, tmp_home: Path) -> None:
    """Full lifecycle: DB exists, audit events, FTS, YAML round-trip."""
    db_path = db_engagement / ".praxis" / "state" / "praxis.db"
    assert db_path.exists()

    # 1. Emit audit events with engagement context
    with set_audit_context(
        profile="default",
        engagement="Test Engagement",
        engagement_path=db_engagement,
    ):
        emit("test.event_one", component="test", subject_id="s1", foo="bar")
        emit("test.event_two", component="test", subject_id="s2", foo="baz")

    # 2. JSONL has events
    audit_file = db_engagement / ".praxis" / "state" / "audit.jsonl"
    lines = audit_file.read_text().splitlines()
    types = [json.loads(line)["event_type"] for line in lines]
    assert "test.event_one" in types
    assert "test.event_two" in types

    # 3. SQLite audit mirror has events
    audit_repo = AuditRepo(db_path)
    rows = audit_repo.list(limit=100)
    row_types = {r.event_type for r in rows}
    assert "test.event_one" in row_types
    assert "test.event_two" in row_types

    # 4. FTS works on messages
    sess_repo = SessionRepo(db_path)
    msg_repo = MessageRepo(db_path)
    sess = Session(id=str(uuid.uuid4()), profile="default", started_at=_now())
    sess_repo.create(sess)
    msg_repo.create(
        Message(
            id=str(uuid.uuid4()),
            session_id=sess.id,
            turn=1,
            role=MessageRole.USER,
            content="hello world stakeholder analysis",
            created_at=_now(),
        )
    )
    hits = msg_repo.fts_search("stakeholder")
    assert len(hits) == 1

    # 5. Round-trip YAML with typed helpers
    glossary_path = db_engagement / ".praxis" / "engagement" / "glossary.yaml"
    write_yaml_typed(glossary_path, Glossary(terms=[Term(term="foo", definition="a test term")]))
    loaded = read_yaml_typed(glossary_path, Glossary)
    assert loaded.terms[0].term == "foo"
    assert loaded.terms[0].definition == "a test term"

    # 6. Work-items CRUD
    wi_repo = WorkItemRepo(db_path)
    now = _now()
    item = WorkItem(
        id=str(uuid.uuid4()),
        type="question",
        status=WorkItemStatus.PENDING,
        priority=WorkItemPriority.HIGH,
        payload={"text": "What are the requirements?"},
        created_at=now,
        updated_at=now,
    )
    wi_repo.create(item)
    loaded_item = wi_repo.get(item.id)
    assert loaded_item is not None
    assert loaded_item.payload["text"] == "What are the requirements?"

    # 7. Tail from JSONL works
    events = tail(audit_file, n=10)
    assert len(events) >= 2
    assert all(isinstance(e, AuditEvent) for e in events)


def test_db_created_on_engagement_init(db_engagement: Path) -> None:
    """Verify that init_engagement creates praxis.db with migrations applied."""
    db_path = db_engagement / ".praxis" / "state" / "praxis.db"
    assert db_path.exists()

    # Check that tables exist
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "sessions" in tables
    assert "messages" in tables
    assert "workitems" in tables
    assert "audit" in tables
    assert "_migrations" in tables


def test_migrations_are_idempotent(db_engagement: Path) -> None:
    """Running migrations twice doesn't fail."""
    from praxis.storage.db import run_migrations

    db_path = db_engagement / ".praxis" / "state" / "praxis.db"
    # Already ran once during init. Run again — should apply 0.
    count = run_migrations(db_path)
    assert count == 0
