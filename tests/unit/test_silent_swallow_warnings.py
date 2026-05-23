"""D-061 — Context-builder failures log structured warnings instead of
silently degrading.

Closes Hermes review item #5. Previously the sufficiency-gate context
builder and the priorities-screen section renderers caught broad
``Exception``, swallowed the message, and returned empty / None.
Operators couldn't tell the difference between "the engagement has no
critical questions" and "the repo file is corrupted." Now each failure
calls ``logger.warning(...)`` via structlog so the degradation is
observable.

These tests pin both invariants:
- **observability** — the failure produces a structured warning;
- **resilience** — the function still returns its degraded value.

They patch the module-level ``logger`` directly to assert against
call arguments, which is more robust than capturing structlog's
stream output (which depends on pytest capture-mode interactions).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from praxis.config.engagement import init_engagement


class TestSufficiencySnapshotFailureLogs:
    def test_snapshot_build_failure_logs_warning_and_returns_none(
        self,
        tmp_engagement: Path,
        tmp_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ``build_engagement_snapshot`` raises, the gate must
        (a) log a ``sufficiency.snapshot_build_failed`` warning and
        (b) keep working by returning ``None``."""
        init_engagement(tmp_engagement, "Test")

        def boom(_path: Path) -> object:
            raise RuntimeError("simulated repo corruption")

        monkeypatch.setattr("praxis.engagement.snapshot.build_engagement_snapshot", boom)

        import praxis.core.sufficiency as sufficiency_mod

        spy = MagicMock(wraps=sufficiency_mod.logger)
        monkeypatch.setattr(sufficiency_mod, "logger", spy)

        result = sufficiency_mod._collect_engagement_context(tmp_engagement)

        # Resilience: function still returns (None means "no context").
        assert result is None

        # Observability: the warning fired with the expected event name + detail.
        warning_calls = [
            call
            for call in spy.warning.call_args_list
            if call.args and call.args[0] == "sufficiency.snapshot_build_failed"
        ]
        assert warning_calls, (
            f"sufficiency.snapshot_build_failed warning was not emitted. "
            f"spy.warning calls: {spy.warning.call_args_list!r}"
        )
        call = warning_calls[0]
        assert call.kwargs.get("error") == "simulated repo corruption"
        assert call.kwargs.get("exc_info") is True


class TestPrioritiesSectionFailureLogs:
    def test_critical_questions_section_load_failure_is_observable(
        self,
        tmp_engagement: Path,
        tmp_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When ``OpenQuestionsRepo.list_all()`` raises during the
        critical-questions section render, the screen must (a) log a
        structured warning and (b) render a dim '⚠ Could not load' marker
        instead of looking like an empty section."""
        init_engagement(tmp_engagement, "Test")

        from praxis.engagement.repos.questions import OpenQuestionsRepo

        def boom(self: OpenQuestionsRepo) -> object:
            raise RuntimeError("YAML decode failed")

        monkeypatch.setattr(OpenQuestionsRepo, "list_all", boom)

        import praxis.tui.screens.priorities_screen as ps_mod

        spy = MagicMock(wraps=ps_mod.logger)
        monkeypatch.setattr(ps_mod, "logger", spy)

        screen = ps_mod.PrioritiesScreen(tmp_engagement)
        rendered = screen._render_critical_questions()

        # Observability — log line.
        warning_calls = [
            c
            for c in spy.warning.call_args_list
            if c.args
            and c.args[0] == "priorities.section_load_failed"
            and c.kwargs.get("section") == "critical_questions"
        ]
        assert warning_calls, (
            f"priorities.section_load_failed[critical_questions] warning "
            f"was not emitted. calls: {spy.warning.call_args_list!r}"
        )
        assert warning_calls[0].kwargs.get("error") == "YAML decode failed"

        # User-visible degradation marker.
        assert "Could not load" in rendered, (
            f"Section rendered without the ⚠ marker; got: {rendered!r}"
        )
        assert "YAML decode failed" in rendered

    def test_top_workitems_section_load_failure_is_observable(
        self,
        tmp_engagement: Path,
        tmp_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Same shape for the work-items section (different repo)."""
        init_engagement(tmp_engagement, "Test")

        from praxis.workqueue.repo import WorkQueueRepo

        def boom(self: WorkQueueRepo, *args: object, **kwargs: object) -> object:
            raise RuntimeError("DB locked")

        monkeypatch.setattr(WorkQueueRepo, "list", boom)

        import praxis.tui.screens.priorities_screen as ps_mod

        spy = MagicMock(wraps=ps_mod.logger)
        monkeypatch.setattr(ps_mod, "logger", spy)

        screen = ps_mod.PrioritiesScreen(tmp_engagement)
        rendered = screen._render_top_workitems()

        warning_calls = [
            c
            for c in spy.warning.call_args_list
            if c.args
            and c.args[0] == "priorities.section_load_failed"
            and c.kwargs.get("section") == "top_workitems"
        ]
        assert warning_calls, (
            f"priorities.section_load_failed[top_workitems] warning was not emitted. "
            f"calls: {spy.warning.call_args_list!r}"
        )

        assert "Could not load" in rendered
        assert "DB locked" in rendered
