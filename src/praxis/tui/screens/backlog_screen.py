"""BacklogScreen — backlog and artifact overview."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

_ARTIFACT_DIRS = ("stories", "specs", "reports", "matrices")


@dataclass(frozen=True)
class BacklogEntry:
    """A backlog-screen row, currently backed by an artifact file."""

    key: str
    kind: str
    title: str
    path: Path
    preview: str


class BacklogDetail(Static):
    """Right pane showing selected backlog/artifact details."""

    DEFAULT_CSS = """
    BacklogDetail {
        width: 45%;
        padding: 1 2;
        border-left: tall $accent;
    }
    """

    def update_entry(self, entry: BacklogEntry | None) -> None:
        if entry is None:
            self.update("[dim]Select an artifact to preview it.[/dim]")
            return
        self.update(
            f"[bold]{entry.title}[/bold]\n"
            f"[bold]Type:[/bold] {entry.kind}\n"
            f"[bold]Path:[/bold] {entry.path}\n\n"
            f"{entry.preview}"
        )


class BacklogScreen(Screen[None]):
    """Backlog and artifact screen."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    BacklogScreen {
        layout: horizontal;
    }
    #backlog-table-container {
        width: 55%;
    }
    """

    def __init__(self, engagement_path: Path) -> None:
        super().__init__()
        self._engagement_path = engagement_path
        self._entries: list[BacklogEntry] = []
        self.backlog_text = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="backlog-table-container"):
                yield DataTable(id="backlog-table")
            yield BacklogDetail(id="backlog-detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#backlog-table", DataTable)
        table.add_columns("Type", "Title", "Path")
        table.cursor_type = "row"
        self._load_entries()

    def _load_entries(self) -> None:
        self._entries = self._discover_artifacts()
        self.backlog_text = "\n".join(f"{entry.kind}: {entry.title} — {entry.path}" for entry in self._entries)

        table = self.query_one("#backlog-table", DataTable)
        table.clear()
        for entry in self._entries:
            table.add_row(entry.kind, entry.title, str(entry.path), key=entry.key)

        detail = self.query_one("#backlog-detail", BacklogDetail)
        detail.update_entry(self._entries[0] if self._entries else None)

    def _discover_artifacts(self) -> list[BacklogEntry]:
        root = self._engagement_path / ".praxis" / "artifacts"
        entries: list[BacklogEntry] = []
        for kind in _ARTIFACT_DIRS:
            directory = root / kind
            if not directory.exists():
                continue
            for path in sorted(directory.glob("**/*")):
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                preview = text[:2000]
                entries.append(
                    BacklogEntry(
                        key=str(path),
                        kind=kind,
                        title=path.name,
                        path=path,
                        preview=preview,
                    )
                )
        return entries

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        detail = self.query_one("#backlog-detail", BacklogDetail)
        if event.row_key and event.row_key.value:
            entry = next((item for item in self._entries if item.key == event.row_key.value), None)
            detail.update_entry(entry)

    def action_refresh(self) -> None:
        self._load_entries()
