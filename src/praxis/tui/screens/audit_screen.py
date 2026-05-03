"""AuditScreen — live tail of audit events."""

from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog


class AuditScreen(Screen[None]):
    """Live tail of engagement audit events."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    AuditScreen {
        layout: vertical;
    }
    #audit-log {
        height: 1fr;
        border: tall $accent;
        padding: 1;
    }
    """

    def __init__(self, engagement_path: Path) -> None:
        super().__init__()
        self._engagement_path = engagement_path
        self._audit_path = engagement_path / ".praxis" / "state" / "audit.jsonl"

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="audit-log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self._load_events()

    def _load_events(self, limit: int = 50) -> None:
        log = self.query_one("#audit-log", RichLog)
        log.clear()

        if not self._audit_path.exists():
            log.write("[dim]No audit events yet.[/dim]")
            return

        lines = self._audit_path.read_text(encoding="utf-8").strip().split("\n")
        recent = lines[-limit:]

        for line in recent:
            try:
                event = json.loads(line)
                ts = event.get("timestamp", "?")
                etype = event.get("event_type", "?")
                actor = event.get("actor", "?")
                subject = event.get("subject_id", "")
                log.write(f"[dim]{ts}[/dim] [{actor}] [bold]{etype}[/bold] {subject}")
            except json.JSONDecodeError:
                continue

    def action_refresh(self) -> None:
        self._load_events()
