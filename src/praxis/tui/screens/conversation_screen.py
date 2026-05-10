"""ConversationScreen — chat with the agent."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog

from praxis.core.chat_runtime import ChatRuntime
from praxis.core.models import StreamEvent

ChatRuntimeFactory = Callable[..., Any]


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

    def __init__(
        self,
        engagement_path: Path,
        *,
        profile_name: str = "default",
        model_alias: str | None = None,
        runtime_factory: ChatRuntimeFactory | None = None,
    ) -> None:
        super().__init__()
        self._engagement_path = engagement_path
        self._profile_name = profile_name
        self._model_alias = model_alias
        self._runtime_factory = runtime_factory or ChatRuntime.create
        self._runtime: Any | None = None
        self.transcript_text = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True)
        yield Input(placeholder="Type a message...", id="chat-input")
        yield Footer()

    def on_mount(self) -> None:
        self._write("[dim]Conversation screen. Type a message below.[/dim]")

    def on_unmount(self) -> None:
        if self._runtime is not None:
            self._runtime.close()
            self._runtime = None

    def _get_runtime(self) -> Any:
        if self._runtime is None:
            self._runtime = self._runtime_factory(
                profile_name=self._profile_name,
                engagement_path=self._engagement_path,
                model_alias=self._model_alias,
            )
            self._runtime.start()
        return self._runtime

    def _write(self, text: str) -> None:
        self.transcript_text += text + "\n"
        log = self.query_one("#chat-log", RichLog)
        log.write(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return
        event.input.clear()
        self._write(f"[bold cyan]You:[/bold cyan] {user_text}")

        if user_text.startswith("/"):
            self._handle_slash(user_text)
            return

        event.input.disabled = True
        self.run_worker(lambda: self._stream_message(user_text, event.input), thread=True)

    def _handle_slash(self, command: str) -> None:
        try:
            result = self._get_runtime().handle_slash(command)
        except Exception as exc:  # noqa: BLE001
            self._write(f"[red]Slash command failed:[/red] {exc}")
            return
        if result.text:
            self._write(result.text)
        if not result.continue_session:
            self.app.exit()

    def _stream_message(self, user_text: str, input_widget: Input) -> None:
        try:
            runtime = self._get_runtime()
            for event in runtime.stream_turn(user_text):
                self.app.call_from_thread(self._render_event, event)
        except Exception as exc:  # noqa: BLE001
            self.app.call_from_thread(self._write, f"[red]Agent error:[/red] {exc}")
        finally:
            self.app.call_from_thread(self._enable_input, input_widget)

    def _enable_input(self, input_widget: Input) -> None:
        input_widget.disabled = False
        input_widget.focus()

    def _render_event(self, event: StreamEvent) -> None:
        if event.type == "text_delta" and event.text:
            self._write(event.text)
        elif event.type == "tool_call_start":
            self._write(f"[dim]⚙ {event.tool_name}[/dim]")
        elif event.type == "tool_result":
            marker = "[red]✗[/red]" if event.is_error else "[green]✓[/green]"
            self._write(marker)
        elif event.type == "done":
            self._write("")

    def action_refresh(self) -> None:
        self._write("[dim]Refreshed.[/dim]")
