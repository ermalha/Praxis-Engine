"""Tests for TUI screens and app — uses Textual's Pilot test driver."""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.core.models import StreamEvent
from praxis.engagement.repos.glossary import GlossaryRepo
from praxis.engagement.repos.stakeholders import StakeholderRepo
from praxis.storage.db import close_connection
from praxis.workqueue import WorkItemPriority, WorkItemType, WorkQueueRepo

textual = pytest.importorskip("textual")

from praxis.tui.app import PraxisApp  # noqa: E402
from praxis.tui.screens.audit_screen import AuditScreen  # noqa: E402
from praxis.tui.screens.conversation_screen import ConversationScreen  # noqa: E402
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
    yield eng_dir
    close_connection(eng_dir / ".praxis" / "state" / "praxis.db")


@pytest.fixture()
def populated_eng(eng: Path) -> Path:
    """Engagement with some data for TUI testing."""
    StakeholderRepo(eng).add(name="Alice", role="PM")
    GlossaryRepo(eng).add_term(term="API", definition="Application Programming Interface")
    repo = WorkQueueRepo(eng)
    repo.enqueue(
        type=WorkItemType.SEND_MESSAGE,
        assignee="human",
        title="Send intro email",
        description="Introduce yourself to the team",
        priority=WorkItemPriority.HIGH,
        rationale="Onboarding",
    )
    return eng


# ---------------------------------------------------------------------------
# App tests
# ---------------------------------------------------------------------------


class TestPraxisApp:
    @pytest.mark.asyncio()
    async def test_app_launches_and_quits(self, populated_eng: Path) -> None:
        app = PraxisApp(engagement_path=populated_eng)
        async with app.run_test() as pilot:
            assert isinstance(app.screen, WorkQueueScreen)
            await pilot.press("q")

    @pytest.mark.asyncio()
    async def test_switch_to_engagement(self, populated_eng: Path) -> None:
        app = PraxisApp(engagement_path=populated_eng)
        async with app.run_test() as pilot:
            await pilot.press("3")
            assert isinstance(app.screen, EngagementScreen)
            await pilot.press("q")

    @pytest.mark.asyncio()
    async def test_switch_to_conversation(self, populated_eng: Path) -> None:
        app = PraxisApp(engagement_path=populated_eng)
        async with app.run_test() as pilot:
            await pilot.press("2")
            assert isinstance(app.screen, ConversationScreen)
            await pilot.press("q")

    @pytest.mark.asyncio()
    async def test_switch_to_audit(self, populated_eng: Path) -> None:
        app = PraxisApp(engagement_path=populated_eng)
        async with app.run_test() as pilot:
            await pilot.press("4")
            assert isinstance(app.screen, AuditScreen)
            await pilot.press("q")

    @pytest.mark.asyncio()
    async def test_help_notification(self, populated_eng: Path) -> None:
        app = PraxisApp(engagement_path=populated_eng)
        async with app.run_test() as pilot:
            await pilot.press("question_mark")
            # Help notification should show without crashing
            await pilot.press("q")


# ---------------------------------------------------------------------------
# Screen tests
# ---------------------------------------------------------------------------


class TestWorkQueueScreen:
    @pytest.mark.asyncio()
    async def test_renders_items(self, populated_eng: Path) -> None:
        app = PraxisApp(engagement_path=populated_eng)
        async with app.run_test() as pilot:
            # The queue screen should show our work-item
            table = app.screen.query_one("#queue-table")
            assert table.row_count >= 1
            await pilot.press("q")


class TestEngagementScreen:
    @pytest.mark.asyncio()
    async def test_renders_stakeholders(self, populated_eng: Path) -> None:
        app = PraxisApp(engagement_path=populated_eng)
        async with app.run_test() as pilot:
            await pilot.press("3")
            table = app.screen.query_one("#stakeholders-table")
            assert table.row_count >= 1
            await pilot.press("q")


class FakeRuntime:
    def __init__(self) -> None:
        self.started = 0
        self.closed = 0
        self.messages: list[str] = []

    def start(self) -> str:
        self.started += 1
        return "fake-session"

    def close(self) -> None:
        self.closed += 1

    def stream_turn(self, user_input: str):
        self.messages.append(user_input)
        yield StreamEvent(type="text_delta", text="Hello from backend")
        yield StreamEvent(type="done")

    def handle_slash(self, command: str):
        from praxis.core.chat_runtime import SlashResult

        return SlashResult(continue_session=True, text=f"handled {command}")


class TestConversationScreenBackend:
    @pytest.mark.asyncio()
    async def test_submit_streams_from_backend_runtime(self, populated_eng: Path) -> None:
        fake = FakeRuntime()
        app = PraxisApp(
            engagement_path=populated_eng,
            chat_runtime_factory=lambda **_: fake,
        )

        async with app.run_test() as pilot:
            await pilot.press("2")
            screen = app.screen
            assert isinstance(screen, ConversationScreen)
            input_widget = screen.query_one("#chat-input")
            input_widget.focus()
            input_widget.value = "hello"

            await pilot.press("enter")
            await pilot.pause()

            assert fake.started == 1
            assert fake.messages == ["hello"]
            assert "Hello from backend" in screen.transcript_text
            await pilot.press("q")

    @pytest.mark.asyncio()
    async def test_slash_command_uses_runtime(self, populated_eng: Path) -> None:
        fake = FakeRuntime()
        app = PraxisApp(
            engagement_path=populated_eng,
            chat_runtime_factory=lambda **_: fake,
        )

        async with app.run_test() as pilot:
            await pilot.press("2")
            screen = app.screen
            assert isinstance(screen, ConversationScreen)
            input_widget = screen.query_one("#chat-input")
            input_widget.focus()
            input_widget.value = "/help"

            await pilot.press("enter")
            await pilot.pause()

            assert "handled /help" in screen.transcript_text
            await pilot.press("q")
