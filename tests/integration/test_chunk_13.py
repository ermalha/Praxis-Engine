"""Integration tests for chunk 13 — TUI.

Uses Textual's Pilot test driver to verify screen navigation
and data rendering.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.engagement.repos.glossary import GlossaryRepo
from praxis.engagement.repos.stakeholders import StakeholderRepo
from praxis.storage.db import close_connection
from praxis.workqueue import WorkItemPriority, WorkItemType, WorkQueueRepo

textual = pytest.importorskip("textual")

from praxis.tui.app import PraxisApp  # noqa: E402
from praxis.tui.screens.engagement_screen import EngagementScreen  # noqa: E402
from praxis.tui.screens.queue_screen import WorkQueueScreen  # noqa: E402


@pytest.fixture()
def eng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    praxis_home = tmp_path / ".praxis"
    praxis_home.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRAXIS_HOME", str(praxis_home))
    monkeypatch.delenv("PRAXIS_PROFILE", raising=False)

    eng_dir = tmp_path / "test-engagement"
    eng_dir.mkdir()
    init_engagement(eng_dir, "Test Engagement")

    # Populate with data
    StakeholderRepo(eng_dir).add(name="Maria L.", role="AP Lead")
    GlossaryRepo(eng_dir).add_term(term="BA", definition="Business Analysis")
    repo = WorkQueueRepo(eng_dir)
    repo.enqueue(
        type=WorkItemType.SEND_MESSAGE,
        assignee="human",
        title="Send follow-up email",
        description="Follow up on outstanding question",
        priority=WorkItemPriority.HIGH,
        rationale="Stalled question",
    )

    yield eng_dir
    close_connection(eng_dir / ".praxis" / "state" / "praxis.db")


@pytest.mark.asyncio()
async def test_tui_smoke(eng: Path) -> None:
    """App launches, shows queue screen by default, navigates, and quits."""
    app = PraxisApp(engagement_path=eng)
    async with app.run_test() as pilot:
        # Default screen is queue
        assert isinstance(app.screen, WorkQueueScreen)

        # Press 3 to go to engagement screen
        await pilot.press("3")
        assert isinstance(app.screen, EngagementScreen)

        # Press q to quit
        await pilot.press("q")
    # No exceptions means success


@pytest.mark.asyncio()
async def test_queue_shows_items(eng: Path) -> None:
    """Queue screen displays the work-items from the repo."""
    app = PraxisApp(engagement_path=eng)
    async with app.run_test() as pilot:
        table = app.screen.query_one("#queue-table")
        assert table.row_count >= 1
        await pilot.press("q")
