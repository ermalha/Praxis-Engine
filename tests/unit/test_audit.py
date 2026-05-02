"""Tests for the audit subsystem."""

from __future__ import annotations

import json
from pathlib import Path

from praxis.audit import AuditEvent, emit, query, set_audit_context, tail


class TestAuditEmit:
    def test_emits_to_global_log(self, tmp_home: Path) -> None:
        event = emit("test.basic", component="test", subject_id="s1", detail="hello")
        assert isinstance(event, AuditEvent)
        assert event.event_type == "test.basic"
        assert event.payload == {"detail": "hello"}

        global_log = tmp_home / "audit.jsonl"
        assert global_log.exists()
        lines = global_log.read_text().splitlines()
        assert len(lines) >= 1
        data = json.loads(lines[-1])
        assert data["event_type"] == "test.basic"

    def test_emits_to_engagement_log_with_context(
        self, db_engagement: Path, tmp_home: Path
    ) -> None:
        with set_audit_context(
            profile="alice",
            engagement="Test Engagement",
            engagement_path=db_engagement,
        ):
            event = emit("test.context", component="test")

        assert event.profile == "alice"
        assert event.engagement == "Test Engagement"

        eng_log = db_engagement / ".praxis" / "state" / "audit.jsonl"
        assert eng_log.exists()
        lines = eng_log.read_text().splitlines()
        # At least our event (there may be init events too)
        types = [json.loads(line)["event_type"] for line in lines]
        assert "test.context" in types

    def test_explicit_overrides_context(self, tmp_home: Path) -> None:
        with set_audit_context(profile="ctx-profile"):
            event = emit("test.override", component="test", profile="explicit-profile")
        assert event.profile == "explicit-profile"


class TestAuditTail:
    def test_tail_returns_recent(self, tmp_home: Path) -> None:
        for i in range(5):
            emit(f"test.event_{i}", component="test")
        global_log = tmp_home / "audit.jsonl"
        events = tail(global_log, n=3)
        assert len(events) == 3

    def test_tail_empty_file(self, tmp_path: Path) -> None:
        events = tail(tmp_path / "nonexistent.jsonl")
        assert events == []


class TestAuditQuery:
    def test_query_by_type(self, tmp_home: Path) -> None:
        emit("type.a", component="test")
        emit("type.b", component="test")
        emit("type.a", component="test")
        global_log = tmp_home / "audit.jsonl"
        results = query(global_log, event_type="type.a")
        assert len(results) == 2
        assert all(e.event_type == "type.a" for e in results)

    def test_query_empty(self, tmp_path: Path) -> None:
        results = query(tmp_path / "nope.jsonl", event_type="anything")
        assert results == []
