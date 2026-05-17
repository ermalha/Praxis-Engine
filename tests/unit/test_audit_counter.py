"""Unit tests for ``praxis.audit.counted`` event counter (D-035)."""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.audit import counted, emit


@pytest.fixture(autouse=True)
def _isolate_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect global audit log to a temp dir so tests don't pollute ~/.praxis."""
    home = tmp_path / "praxis-home"
    home.mkdir()
    monkeypatch.setenv("PRAXIS_HOME", str(home))


class TestAuditCounter:
    def test_counts_emits_inside_block(self) -> None:
        with counted() as c:
            emit("test.event_a")
            emit("test.event_b")
            emit("test.event_c")
        assert c.value == 3

    def test_zero_when_no_emits_in_block(self) -> None:
        with counted() as c:
            pass
        assert c.value == 0

    def test_emit_outside_block_does_not_affect_anything(self) -> None:
        # Just emitting outside any counted() block should not raise.
        emit("test.standalone")
        with counted() as c:
            emit("test.inside")
        assert c.value == 1

    def test_nested_inner_replaces_outer_during_inner(self) -> None:
        """Per the documented semantic: inner counter is active inside; the
        outer resumes its own counting after the inner exits."""
        with counted() as outer:
            emit("test.outer_pre")  # counted by outer (1)
            with counted() as inner:
                emit("test.inner_a")  # counted by inner only (1)
                emit("test.inner_b")  # counted by inner only (2)
            emit("test.outer_post")  # counted by outer (2)
        assert inner.value == 2
        assert outer.value == 2
