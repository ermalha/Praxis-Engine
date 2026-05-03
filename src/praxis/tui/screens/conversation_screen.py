"""ConversationScreen — chat with the agent."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog


class ConversationScreen(Screen[None]):
    """Chat interface wrapping the Praxis agent."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    ConversationScreen {
        layout: vertical;
    }
    #chat-log {
        height: 1fr;
        border: tall $accent;
        padding: 1;
    }
    #chat-input {
        dock: bottom;
        margin: 1 0 0 0;
    }
    """

    def __init__(self, engagement_path: Path) -> None:
        super().__init__()
        self._engagement_path = engagement_path

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="chat-log", highlight=True, markup=True)
        yield Input(placeholder="Type a message...", id="chat-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write("[dim]Conversation screen. Type a message below.[/dim]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return
        event.input.clear()

        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold cyan]You:[/bold cyan] {user_text}")
        log.write("[dim]Agent processing...[/dim]")

    def action_refresh(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write("[dim]Refreshed.[/dim]")
