"""Smoke tests for the live-refresh TUI screens (D-044).

These tests stay at the introspection level — Textual driver tests
require an async ``pilot`` fixture, which is heavier than the v0.3.0
minimum needs. We verify:

- The expected refresh action and keybinding are wired up.
- ``on_mount`` contains the ``set_interval`` call (source-level check).
- The TUI smoke command still loads.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.tui.screens.backlog_screen import BacklogScreen
from praxis.tui.screens.priorities_screen import PrioritiesScreen
from praxis.tui.screens.queue_screen import WorkQueueScreen

runner = CliRunner()


def _has_binding(screen_cls: type, key: str, action: str) -> bool:
    for binding in screen_cls.BINDINGS:
        if isinstance(binding, tuple) and binding[0] == key and binding[1].startswith(action):
            return True
    return False


class TestBacklogScreenLiveRefresh:
    def test_has_refresh_binding(self) -> None:
        assert _has_binding(BacklogScreen, "r", "refresh")

    def test_has_refresh_action(self) -> None:
        assert callable(getattr(BacklogScreen, "action_refresh", None))

    def test_on_mount_installs_interval(self) -> None:
        """D-044: on_mount must wire set_interval so the screen auto-refreshes."""
        src = inspect.getsource(BacklogScreen.on_mount)
        assert "set_interval" in src
        assert "_load_entries" in src


class TestWorkQueueScreenLiveRefresh:
    def test_has_refresh_binding(self) -> None:
        assert _has_binding(WorkQueueScreen, "r", "refresh")

    def test_has_refresh_action(self) -> None:
        assert callable(getattr(WorkQueueScreen, "action_refresh", None))

    def test_on_mount_installs_interval(self) -> None:
        src = inspect.getsource(WorkQueueScreen.on_mount)
        assert "set_interval" in src
        assert "_load_items" in src


class TestPrioritiesScreen:
    def test_has_refresh_binding(self) -> None:
        assert _has_binding(PrioritiesScreen, "r", "refresh")

    def test_has_refresh_action(self) -> None:
        assert callable(getattr(PrioritiesScreen, "action_refresh", None))

    def test_on_mount_installs_interval(self) -> None:
        src = inspect.getsource(PrioritiesScreen.on_mount)
        assert "set_interval" in src
        assert "_reload" in src

    def test_reload_no_errors_on_empty_engagement(self, tmp_engagement: Path) -> None:
        """D-045: section renderers tolerate missing repos / no sufficiency reports."""
        init_engagement(tmp_engagement, "Test")
        screen = PrioritiesScreen(tmp_engagement)
        # Just exercise the renderers; they must not raise.
        assert "Top critical open questions" in screen._render_critical_questions()
        assert "Oldest unanswered questions" in screen._render_oldest_unanswered()
        assert "Top active work items" in screen._render_top_workitems()
        assert "Insufficient artifacts" in screen._render_insufficient_artifacts()


class TestSmokeStillPasses:
    def test_tui_smoke_loads_with_refresh_screens(self, tmp_engagement: Path) -> None:
        """Regression: D-044/045 changes don't break the smoke loader."""
        init_engagement(tmp_engagement, "Test")
        result = runner.invoke(
            app,
            ["tui", "--smoke", "-e", str(tmp_engagement)],
        )
        assert result.exit_code == 0, result.output
        assert "screens_loaded" in result.output
        assert '"status": "ok"' in result.output

    def test_priorities_in_smoke_available_screens(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        result = runner.invoke(
            app,
            ["tui", "--smoke", "--screen", "priorities", "-e", str(tmp_engagement)],
        )
        assert result.exit_code == 0, result.output
        assert '"priorities"' in result.output
        assert '"initial_screen": "priorities"' in result.output
