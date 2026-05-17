"""WorkQueueScreen — prioritized work-queue with detail pane."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

if TYPE_CHECKING:
    pass

from praxis.workqueue import WorkItem, WorkQueueRepo, prioritize


class QueueDetail(Static):
    """Right pane showing details of the selected work-item."""

    DEFAULT_CSS = """
    QueueDetail {
        width: 40%;
        padding: 1 2;
        border-left: tall $accent;
    }
    """

    def update_item(self, item: WorkItem | None) -> None:
        if item is None:
            self.update("[dim]Select an item to see details.[/dim]")
            return
        lines = [
            f"[bold]ID:[/bold] {item.id}",
            f"[bold]Type:[/bold] {item.type.value}",
            f"[bold]Status:[/bold] {item.status.value}",
            f"[bold]Priority:[/bold] {item.priority.value}",
            f"[bold]Assignee:[/bold] {item.assignee}",
            f"[bold]Title:[/bold] {item.title}",
            "",
            f"[bold]Description:[/bold]\n{item.description}",
        ]
        if item.rationale:
            lines.append(f"\n[bold]Rationale:[/bold] {item.rationale}")
        if item.deadline:
            lines.append(f"[bold]Deadline:[/bold] {item.deadline}")
        if item.completion_note:
            lines.append(f"[bold]Note:[/bold] {item.completion_note}")
        self.update("\n".join(lines))


class WorkQueueScreen(Screen[None]):
    """Prioritized work-queue view."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    WorkQueueScreen {
        layout: horizontal;
    }
    #queue-table-container {
        width: 60%;
    }
    """

    def __init__(self, engagement_path: Path) -> None:
        super().__init__()
        self._engagement_path = engagement_path
        self._items: list[WorkItem] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="queue-table-container"):
                yield DataTable(id="queue-table")
            yield QueueDetail(id="queue-detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#queue-table", DataTable)
        table.add_columns("ID", "Priority", "Status", "Assignee", "Title")
        table.cursor_type = "row"
        self._load_items()
        # D-044: auto-refresh as wake/elicit/commit changes the queue.
        self._refresh_timer = self.set_interval(3.0, self._load_items)

    def _load_items(self) -> None:
        repo = WorkQueueRepo(self._engagement_path)
        items = repo.list(limit=100)
        human = [i for i in items if i.assignee == "human"]
        self._items = prioritize(human, active_only=True)

        table = self.query_one("#queue-table", DataTable)
        table.clear()
        for item in self._items:
            table.add_row(
                item.id,
                item.priority.value.upper(),
                item.status.value,
                item.assignee,
                item.title,
                key=item.id,
            )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        detail = self.query_one("#queue-detail", QueueDetail)
        if event.row_key and event.row_key.value:
            item = next((i for i in self._items if i.id == event.row_key.value), None)
            detail.update_item(item)

    def action_refresh(self) -> None:
        self._load_items()
