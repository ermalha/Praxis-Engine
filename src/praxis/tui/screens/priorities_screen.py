"""PrioritiesScreen — "what should I work on now?" view (D-045)."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import structlog
from rich.markup import escape as rich_escape
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

logger = structlog.get_logger(component="tui.priorities")

_MAX_PER_SECTION = 5
_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_ACTIVE_STATUSES = ("queued", "in_progress")
_OPEN_STATUSES = ("open", "asked")


class _Section(Static):
    """A titled section in the priorities view."""

    DEFAULT_CSS = """
    _Section {
        padding: 1 2;
        border-bottom: tall $accent 20%;
    }
    """


class PrioritiesScreen(Screen[None]):
    """Aggregates the analyst's top-of-mind items across the engagement."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    PrioritiesScreen {
        layout: vertical;
    }
    """

    def __init__(self, engagement_path: Path) -> None:
        super().__init__()
        self._engagement_path = engagement_path

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield _Section(id="priorities-critical-questions")
            yield _Section(id="priorities-oldest-unanswered")
            yield _Section(id="priorities-top-workitems")
            yield _Section(id="priorities-insufficient-artifacts")
        yield Footer()

    def on_mount(self) -> None:
        self._reload()
        self._refresh_timer = self.set_interval(3.0, self._reload)

    def action_refresh(self) -> None:
        self._reload()

    # ------------------------------------------------------------------
    # Reload pipeline
    # ------------------------------------------------------------------

    def _reload(self) -> None:
        self.query_one("#priorities-critical-questions", _Section).update(
            self._render_critical_questions()
        )
        self.query_one("#priorities-oldest-unanswered", _Section).update(
            self._render_oldest_unanswered()
        )
        self.query_one("#priorities-top-workitems", _Section).update(self._render_top_workitems())
        self.query_one("#priorities-insufficient-artifacts", _Section).update(
            self._render_insufficient_artifacts()
        )

    # ------------------------------------------------------------------
    # Section renderers
    # ------------------------------------------------------------------

    def _render_critical_questions(self) -> str:
        from praxis.engagement.repos.questions import OpenQuestionsRepo

        lines = ["[bold]Top critical open questions[/bold]"]
        try:
            questions = [
                q
                for q in OpenQuestionsRepo(self._engagement_path).list_all()
                if q.status in _OPEN_STATUSES and q.priority == "critical"
            ]
        except Exception as exc:  # noqa: BLE001 — TUI stays alive on partial repo failures
            # D-061: don't silently degrade. Log it AND show a dim marker so
            # the user knows the section is showing nothing because of an
            # error, not because the section is genuinely empty.
            logger.warning(
                "priorities.section_load_failed",
                section="critical_questions",
                error=str(exc),
                exc_info=True,
            )
            lines.append(f"  [dim]⚠ Could not load: {rich_escape(str(exc))}[/dim]")
            return "\n".join(lines)
        questions.sort(key=lambda q: q.created_at)
        if not questions:
            lines.append("  [dim](none)[/dim]")
        else:
            for q in questions[:_MAX_PER_SECTION]:
                lines.append(f"  - {rich_escape(f'[{q.id}]')} {rich_escape(q.question)}")
        return "\n".join(lines)

    def _render_oldest_unanswered(self) -> str:
        from praxis.engagement.repos.questions import OpenQuestionsRepo

        lines = ["[bold]Oldest unanswered questions[/bold]"]
        try:
            questions = [
                q
                for q in OpenQuestionsRepo(self._engagement_path).list_all()
                if q.status in _OPEN_STATUSES
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "priorities.section_load_failed",
                section="oldest_unanswered",
                error=str(exc),
                exc_info=True,
            )
            lines.append(f"  [dim]⚠ Could not load: {rich_escape(str(exc))}[/dim]")
            return "\n".join(lines)
        questions.sort(key=lambda q: q.created_at)
        if not questions:
            lines.append("  [dim](none)[/dim]")
        else:
            for q in questions[:_MAX_PER_SECTION]:
                age = q.created_at.isoformat(timespec="minutes")
                lines.append(
                    f"  - {rich_escape(f'[{q.priority}]')} {rich_escape(q.question)} "
                    f"[dim](since {age})[/dim]"
                )
        return "\n".join(lines)

    def _render_top_workitems(self) -> str:
        from praxis.workqueue.repo import WorkQueueRepo

        lines = ["[bold]Top active work items[/bold]"]
        try:
            items = WorkQueueRepo(self._engagement_path).list(limit=200)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "priorities.section_load_failed",
                section="top_workitems",
                error=str(exc),
                exc_info=True,
            )
            lines.append(f"  [dim]⚠ Could not load: {rich_escape(str(exc))}[/dim]")
            return "\n".join(lines)
        active = [i for i in items if i.status.value in _ACTIVE_STATUSES]
        active.sort(key=lambda i: (_PRIORITY_RANK.get(i.priority.value, 9), i.created_at))
        if not active:
            lines.append("  [dim](none)[/dim]")
        else:
            for i in active[:_MAX_PER_SECTION]:
                lines.append(
                    f"  - {rich_escape(f'[{i.priority.value.upper()}]')} "
                    f"{rich_escape(i.title)} "
                    f"[dim]({i.assignee}, {i.status.value})[/dim]"
                )
        return "\n".join(lines)

    def _render_insufficient_artifacts(self) -> str:
        lines = ["[bold]Insufficient artifacts needing elicitation[/bold]"]
        reports_dir = self._engagement_path / ".praxis" / "state" / "sufficiency-reports"
        if not reports_dir.is_dir():
            lines.append("  [dim](none)[/dim]")
            return "\n".join(lines)

        insufficient: list[tuple[str, str, str, Path]] = []
        for f in reports_dir.glob("*.json"):
            with contextlib.suppress(json.JSONDecodeError, OSError, KeyError):
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("verdict") != "insufficient":
                    continue
                kind = str(data.get("artifact_kind", "?"))
                target = str(data.get("artifact_target", "?"))
                sort_key = str(data.get("generated_at") or f.stat().st_mtime)
                insufficient.append((sort_key, kind, target, f))

        if not insufficient:
            lines.append("  [dim](none)[/dim]")
            return "\n".join(lines)

        # Newest first
        insufficient.sort(key=lambda t: t[0], reverse=True)
        for _ts, kind, target, path in insufficient[:_MAX_PER_SECTION]:
            lines.append(f"  - {rich_escape(kind)}: {rich_escape(target)} [dim]({path.name})[/dim]")
        return "\n".join(lines)
