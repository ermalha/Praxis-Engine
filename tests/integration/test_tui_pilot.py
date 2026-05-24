"""D-062 — Real Textual pilot tests for the TUI.

Closes the Hermes review's call for real interaction-level coverage:
previous TUI tests only inspected source strings + binding tables (e.g.
``"set_interval" in inspect.getsource(...)``). Those don't catch widget-
ID renames, event-routing bugs, row-selection failures, or post-Textual-
upgrade regressions.

These tests drive ``PraxisApp`` through ``app.run_test()`` and exercise:
- numeric-key screen switching (1 → 9)
- queue / priorities / artifact-viewer renders against a seeded engagement
- ``w``-keybind manual wake invokes ``Orchestrator.wake_once``
- full 1 → 9 sweep produces no exceptions (Textual-upgrade guard)

The seeding helper is shared with ``scripts/gen_screenshots.py`` via
``_tui_seed.py`` so screenshots can't drift from tested behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.tui.app import PraxisApp

from ._tui_seed import (
    DEMO_ARTIFACT_FILENAME,
    DEMO_CRITICAL_QUESTION,
    seed_demo_engagement,
    seed_demo_profile,
)

# Pause windows: Textual pilot is async; widgets mount + refresh-tick on a
# scheduler. These values are tuned to be reliable on CI without being slow.
_INITIAL_SETTLE = 0.5
_SWITCH_SETTLE = 0.3

# Map binding keys → screen class names (the BINDINGS table in app.py).
_KEY_TO_SCREEN_CLASS: dict[str, str] = {
    "1": "WorkQueueScreen",
    "2": "ConversationScreen",
    "3": "EngagementScreen",
    "4": "AuditScreen",
    "5": "BacklogScreen",
    "6": "ConfigScreen",
    "7": "ProjectSetupScreen",
    "8": "PrioritiesScreen",
    "9": "ArtifactViewerScreen",
}


@pytest.fixture()
def seeded_engagement(tmp_engagement: Path, tmp_home: Path) -> Path:
    """A demo engagement + profile, ready for the TUI to render against."""
    seed_demo_profile()
    seed_demo_engagement(tmp_engagement)
    return tmp_engagement


def _make_app(eng_path: Path, *, initial_screen: str = "queue") -> PraxisApp:
    return PraxisApp(
        engagement_path=eng_path,
        profile_name="demo",
        initial_screen=initial_screen,
    )


# ---------------------------------------------------------------------------
# Screen switching
# ---------------------------------------------------------------------------


class TestScreenSwitching:
    async def test_keys_1_to_9_switch_screens(self, seeded_engagement: Path) -> None:
        """Pressing each numeric key activates the screen its binding declares."""
        app = _make_app(seeded_engagement)

        async with app.run_test(size=(132, 40)) as pilot:
            await pilot.pause(_INITIAL_SETTLE)

            for key, expected_cls in _KEY_TO_SCREEN_CLASS.items():
                await pilot.press(key)
                await pilot.pause(_SWITCH_SETTLE)
                actual_cls = type(app.screen).__name__
                assert actual_cls == expected_cls, (
                    f"Key {key!r}: expected screen {expected_cls}, got {actual_cls}. "
                    "Either the BINDINGS table drifted or a screen class was renamed."
                )

    async def test_full_sweep_produces_no_unhandled_exceptions(
        self, seeded_engagement: Path
    ) -> None:
        """1 → 9 sweep with a populated engagement: every screen mounts cleanly.

        Post-Textual-upgrade guard. If any screen's ``on_mount`` or
        first-refresh raises, the pilot context catches it and re-raises here.
        """
        app = _make_app(seeded_engagement)

        async with app.run_test(size=(132, 40)) as pilot:
            await pilot.pause(_INITIAL_SETTLE)
            for key in _KEY_TO_SCREEN_CLASS:
                await pilot.press(key)
                await pilot.pause(_SWITCH_SETTLE)


# ---------------------------------------------------------------------------
# Queue screen
# ---------------------------------------------------------------------------


class TestQueueScreenRenders:
    async def test_queue_screen_shows_seeded_human_work_items(
        self, seeded_engagement: Path
    ) -> None:
        """``#queue-table`` shows the human-assigned seeded items.

        The seeder enqueues 3 items (2 human + 1 agent); the queue screen
        is explicitly the human-action queue and filters to ``assignee ==
        "human"`` (queue_screen.py:93), so we expect 2 rows. Agent items
        surface on the Priorities / Backlog screens instead.
        """
        app = _make_app(seeded_engagement, initial_screen="queue")

        async with app.run_test(size=(132, 40)) as pilot:
            await pilot.pause(_INITIAL_SETTLE)
            await pilot.press("1")
            await pilot.pause(_SWITCH_SETTLE)

            from textual.widgets import DataTable

            # Query the active screen, not the whole app — only the active
            # screen's DOM contains widgets after switch_screen().
            table = app.screen.query_one("#queue-table", DataTable)
            assert table.row_count == 2, (
                f"Expected #queue-table to show 2 human-assigned rows from the "
                f"seed (3 items total: 2 human + 1 agent); got {table.row_count}. "
                "Either the seeder changed or the queue screen's human-only "
                "filter regressed."
            )


# ---------------------------------------------------------------------------
# Priorities screen — Hermes specifically asked for this
# ---------------------------------------------------------------------------


class TestPrioritiesScreenRenders:
    async def test_critical_question_appears_in_rendered_output(
        self, seeded_engagement: Path
    ) -> None:
        """The seeded engagement has one CRITICAL open question; Priorities
        must render it somewhere in its widget tree."""
        app = _make_app(seeded_engagement)

        async with app.run_test(size=(132, 40)) as pilot:
            await pilot.pause(_INITIAL_SETTLE)
            await pilot.press("8")
            await pilot.pause(_SWITCH_SETTLE)

            # Walk all renderable widgets and look for the question text. The
            # exact widget that carries it can change without breaking the
            # contract: "the critical question is visible somewhere on
            # Priorities."
            rendered = _stringify_screen(app)
            assert DEMO_CRITICAL_QUESTION in rendered, (
                f"Critical question text not found in Priorities screen output. "
                f"Rendered (truncated): {rendered[:500]!r}"
            )


# ---------------------------------------------------------------------------
# Artifact Viewer — Hermes specifically asked for row-selection coverage
# ---------------------------------------------------------------------------


class TestArtifactViewer:
    async def test_artifact_viewer_lists_seeded_artifact(self, seeded_engagement: Path) -> None:
        """The seeded engagement has one artifact file; Artifact Viewer's
        ``#artifact-list`` DataTable must list it after switching screens.

        Reads cell content directly via ``get_row_at()`` because DataTable's
        rendered output is a layout primitive — the cell text doesn't surface
        through ``widget.render()`` string conversion.
        """
        app = _make_app(seeded_engagement)

        async with app.run_test(size=(132, 40)) as pilot:
            await pilot.pause(_INITIAL_SETTLE)
            await pilot.press("9")
            await pilot.pause(_SWITCH_SETTLE)

            from textual.widgets import DataTable

            table = app.screen.query_one("#artifact-list", DataTable)
            assert table.row_count >= 1, (
                f"Expected #artifact-list to have >=1 row (one seeded artifact); "
                f"got {table.row_count}."
            )

            # Walk every cell value across every row; the filename should appear.
            stem = DEMO_ARTIFACT_FILENAME.removesuffix(".md")
            row_cells: list[str] = []
            for i in range(table.row_count):
                row_cells.extend(str(c) for c in table.get_row_at(i))

            assert any(stem in c or DEMO_ARTIFACT_FILENAME in c for c in row_cells), (
                f"Seeded artifact not listed in #artifact-list. "
                f"Looking for {stem!r} or {DEMO_ARTIFACT_FILENAME!r} in: {row_cells!r}"
            )


# ---------------------------------------------------------------------------
# Manual wake (w keybind)
# ---------------------------------------------------------------------------


class TestManualWakeKeybind:
    async def test_w_keybind_invokes_orchestrator_wake_once(
        self,
        seeded_engagement: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Pressing ``w`` must call ``Orchestrator.wake_once`` exactly once.

        D-057 already proved the action calls the right ``load_profile``;
        this complements it by going through Pilot's actual key-dispatch
        path instead of calling ``action_manual_wake`` directly.
        """
        from praxis.core.orchestrator import Orchestrator

        wake_calls: list[object] = []
        real_wake_once = Orchestrator.wake_once

        def spy(self: Orchestrator, *args: object, **kwargs: object) -> object:
            wake_calls.append((args, kwargs))
            return real_wake_once(self, *args, **kwargs)

        monkeypatch.setattr(Orchestrator, "wake_once", spy)

        app = _make_app(seeded_engagement)

        async with app.run_test(size=(132, 40)) as pilot:
            await pilot.pause(_INITIAL_SETTLE)
            await pilot.press("w")
            # Wake is synchronous (rule-based) — but the action is dispatched
            # async; pause to let it finish.
            await pilot.pause(_SWITCH_SETTLE)

        assert len(wake_calls) == 1, (
            f"Expected wake_once to be called exactly once; got {len(wake_calls)} calls."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stringify_screen(app: PraxisApp) -> str:
    """Best-effort: collect text from every widget on the active screen.

    Pilot tests can't easily diff rendered TUI output, but they CAN walk
    the widget tree and read each widget's renderable string. That's
    enough to verify "the seeded data is somewhere on this screen."
    """
    parts: list[str] = []
    for widget in app.screen.walk_children(with_self=True):
        # ``render()`` returns a Rich renderable; ``str()`` of it surfaces
        # the text content for assertions.
        try:
            rendered = widget.render()
        except Exception:  # noqa: BLE001 — some widgets don't render outside a layout
            continue
        parts.append(str(rendered))
        # DataTable / similar containers also expose row content via
        # ``rows`` / ``columns`` — fall through.
        for attr in ("text", "value", "renderable"):
            v = getattr(widget, attr, None)
            if v is not None:
                parts.append(str(v))
    return "\n".join(parts)
