"""ArtifactViewerScreen — focused artifact reading with rendered markdown (D-046)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Markdown

_ARTIFACT_DIRS = ("stories", "specs", "reports", "matrices")
_EMPTY_HINT = (
    "## No artifact selected\n\n"
    "Pick an artifact on the left to view its rendered markdown.\n\n"
    "Generate one with `praxis artifact generate scope-brief -e <engagement>`."
)


@dataclass(frozen=True)
class _ArtifactEntry:
    """A row in the artifact list, backed by a file on disk."""

    key: str
    kind: str
    title: str
    path: Path


class ArtifactViewerScreen(Screen[None]):
    """Browse generated artifacts and view their rendered markdown inline."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    ArtifactViewerScreen {
        layout: horizontal;
    }
    #artifact-list-container {
        width: 40%;
    }
    #artifact-md {
        width: 60%;
        padding: 1 2;
        border-left: tall $accent;
    }
    """

    def __init__(self, engagement_path: Path) -> None:
        super().__init__()
        self._engagement_path = engagement_path
        self._entries: list[_ArtifactEntry] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="artifact-list-container"):
                yield DataTable(id="artifact-list")
            yield Markdown(_EMPTY_HINT, id="artifact-md")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#artifact-list", DataTable)
        table.add_columns("Type", "Title")
        table.cursor_type = "row"
        self._load_entries()
        # D-044/D-046: auto-refresh so newly-generated artifacts appear live.
        self._refresh_timer = self.set_interval(3.0, self._load_entries)

    def action_refresh(self) -> None:
        self._load_entries()

    # ------------------------------------------------------------------
    # Reload + selection
    # ------------------------------------------------------------------

    def _load_entries(self) -> None:
        entries = self._discover_artifacts()
        # Preserve the currently-highlighted key when possible.
        table = self.query_one("#artifact-list", DataTable)
        previous_key: str | None = None
        try:
            row_key = table.cursor_row_key  # type: ignore[attr-defined]
            if row_key is not None and row_key.value is not None:
                previous_key = str(row_key.value)
        except Exception:  # noqa: BLE001
            previous_key = None

        self._entries = entries
        table.clear()
        for entry in entries:
            table.add_row(entry.kind, entry.title, key=entry.key)

        if not entries:
            self._render_markdown(None)
            return

        # Re-select previous row if it still exists; else first.
        target = next((e for e in entries if e.key == previous_key), None) if previous_key else None
        self._render_markdown(target or entries[0])

    def _discover_artifacts(self) -> list[_ArtifactEntry]:
        root = self._engagement_path / ".praxis" / "artifacts"
        entries: list[_ArtifactEntry] = []
        for kind in _ARTIFACT_DIRS:
            directory = root / kind
            if not directory.exists():
                continue
            for path in sorted(directory.glob("**/*")):
                if not path.is_file():
                    continue
                entries.append(
                    _ArtifactEntry(
                        key=str(path),
                        kind=kind,
                        title=path.name,
                        path=path,
                    )
                )
        return entries

    def _render_markdown(self, entry: _ArtifactEntry | None) -> None:
        md = self.query_one("#artifact-md", Markdown)
        if entry is None:
            md.update(_EMPTY_HINT)
            return
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = f"# Could not read artifact\n\nPath: `{entry.path}`"
        md.update(text)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value:
            entry = next((e for e in self._entries if e.key == event.row_key.value), None)
            self._render_markdown(entry)
