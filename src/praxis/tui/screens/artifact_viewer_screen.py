"""ArtifactViewerScreen — focused artifact reading with rendered markdown (D-046).

D-067 adds the ``R`` keybind which regenerates the selected artifact via
the same kind it was originally produced under. The new artifact lands
as a fresh timestamped file alongside the old one — the original is
never overwritten so the audit trail is preserved.

The LLM round-trip is wrapped in a ``@work(thread=True)`` worker so the
UI thread stays responsive during the regenerate call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import structlog
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Markdown

logger = structlog.get_logger(component="tui.artifact_viewer")

_ARTIFACT_DIRS = ("stories", "specs", "reports", "matrices")
_EMPTY_HINT = (
    "## No artifact selected\n\n"
    "Pick an artifact on the left to view its rendered markdown.\n\n"
    "Generate one with `praxis artifact generate scope-brief -e <engagement>`."
)

# Filenames look like ``<kind-slug>-YYYYMMDDTHHMMSSZ.md`` (artifacts.service._slug
# + datetime suffix). This pattern unwinds the suffix so we can recover the
# original kind from a row's filename for regenerate.
_FILENAME_TIMESTAMP_RE = re.compile(r"-\d{8}T\d{6}Z\.md$")


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
        # D-067: capital-R regenerates the currently-highlighted artifact.
        # Lowercase ``r`` stays bound to refresh-the-list (D-046) so muscle
        # memory from v0.3.x keeps working.
        ("R", "regenerate", "Regenerate"),
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

    def __init__(
        self,
        engagement_path: Path,
        *,
        profile_name: str | None = None,
        model_alias: str | None = None,
    ) -> None:
        super().__init__()
        self._engagement_path = engagement_path
        self._profile_name = profile_name
        self._model_alias = model_alias
        self._entries: list[_ArtifactEntry] = []
        # D-067: track the row-highlighted entry directly. ``DataTable.
        # cursor_row_key`` was unreliable across Textual versions, so the
        # screen now keeps its own ref and updates it on
        # ``on_data_table_row_highlighted``. After ``_load_entries`` the
        # first entry is the default selection.
        self._highlighted: _ArtifactEntry | None = None

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
    # D-067 — Regenerate the selected artifact
    # ------------------------------------------------------------------

    def action_regenerate(self) -> None:
        """Regenerate the currently-highlighted artifact via the LLM.

        Spawns a worker thread so the UI doesn't freeze during the LLM
        call. The new artifact lands as a fresh timestamped file; the
        existing artifact is preserved.
        """
        entry = self._current_entry()
        if entry is None:
            self.notify("No artifact selected.", severity="warning")
            return
        if self._profile_name is None:
            self.notify(
                "Cannot regenerate: TUI was launched without a profile.",
                severity="error",
            )
            return

        kind = _recover_kind_from_filename(entry.title)
        self.notify(f"Regenerating {kind}…", title="Regenerate")
        self._do_regenerate(kind)

    @work(thread=True, exclusive=True)  # type: ignore[misc]
    def _do_regenerate(self, kind: str) -> None:
        """Worker: run the LLM round-trip off the UI thread."""
        try:
            from praxis.artifacts.service import generate_artifact
            from praxis.config.loader import load_profile, resolve_model_config
            from praxis.transport import make_transport

            assert self._profile_name is not None  # narrowed in action_regenerate
            profile = load_profile(self._profile_name)
            model_config = resolve_model_config(profile, None, self._model_alias)
            transport = make_transport(model_config)

            result = generate_artifact(
                engagement_path=self._engagement_path,
                profile=profile,
                model=model_config.model,
                transport=transport,
                artifact_kind=kind,
                prompt="Regenerate this artifact using current engagement state.",
            )
            self.app.call_from_thread(self._on_regenerate_complete, Path(result.path).name)
        except Exception as exc:  # noqa: BLE001 — surface via notify
            logger.warning(
                "tui.regenerate_failed",
                kind=kind,
                error=str(exc),
                exc_info=True,
            )
            self.app.call_from_thread(self._on_regenerate_failed, str(exc))

    def _on_regenerate_complete(self, new_filename: str) -> None:
        self.notify(f"Wrote {new_filename}", title="Regenerate")
        self._load_entries()

    def _on_regenerate_failed(self, message: str) -> None:
        self.notify(f"Regenerate failed: {message}", severity="error")

    def _current_entry(self) -> _ArtifactEntry | None:
        """Return the currently-highlighted entry, or None."""
        return self._highlighted

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
        chosen = target or entries[0]
        self._highlighted = chosen
        self._render_markdown(chosen)

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
            self._highlighted = entry
            self._render_markdown(entry)


def _recover_kind_from_filename(filename: str) -> str:
    """Strip the ``-YYYYMMDDTHHMMSSZ.md`` suffix to recover the original kind.

    Falls back to the filename stem (drops ``.md`` only) if the timestamp
    suffix isn't present (e.g. a manually-named file in the artifacts
    directory).
    """
    stripped = _FILENAME_TIMESTAMP_RE.sub("", filename)
    if stripped != filename:
        return stripped
    return Path(filename).stem
