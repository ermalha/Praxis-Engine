"""ProjectSetupScreen — guidance for initializing/configuring a project from TUI."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


class ProjectSetupScreen(Screen[None]):
    """Project setup guidance screen.

    This is intentionally read-only for v0.2.0: it gives safe, copyable commands
    and avoids collecting raw API keys inside the TUI.
    """

    def __init__(self, engagement_path: Path | None = None) -> None:
        super().__init__()
        self._engagement_path = engagement_path
        self.setup_text = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="project-setup-body")
        yield Footer()

    def on_mount(self) -> None:
        current = self._engagement_path or Path.cwd()
        self.setup_text = "\n".join(
            [
                "[bold]Project Setup[/bold]",
                "",
                f"Current path: {current}",
                "",
                "Create a new engagement:",
                "  mkdir -p ~/engagements/my-project",
                "  cd ~/engagements/my-project",
                "  uv run --project /root/praxis-realworld-eval/repo praxis init \\",
                "    --name 'My Project' --methodology agile",
                "",
                "Configure OpenRouter:",
                "  export OPENROUTER_API_KEY=...",
                "  uv run --project /root/praxis-realworld-eval/repo praxis profile create \\",
                "    realworld --provider openrouter --model anthropic/claude-sonnet-4 \\",
                "    --api-key-env OPENROUTER_API_KEY --set-default",
                "",
                "Launch this TUI:",
                "  PRAXIS_HOME=/root/praxis-realworld-eval/praxis-home \\",
                "    uv run --project /root/praxis-realworld-eval/repo praxis tui \\",
                "    --engagement <path>",
                "",
                "v0.2.0 avoids typing raw keys into the TUI. Put keys in the",
                "shell/service environment and store only env var names in profiles.",
            ]
        )
        self.query_one("#project-setup-body", Static).update(self.setup_text)
