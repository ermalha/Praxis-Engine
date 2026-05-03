"""EngagementScreen — browse engagement model data."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, TabbedContent, TabPane


class EngagementScreen(Screen[None]):
    """Tabbed browser for engagement model entities."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    EngagementScreen {
        layout: vertical;
    }
    """

    def __init__(self, engagement_path: Path) -> None:
        super().__init__()
        self._engagement_path = engagement_path

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Stakeholders", id="tab-stakeholders"):
                yield DataTable(id="stakeholders-table")
            with TabPane("Questions", id="tab-questions"):
                yield DataTable(id="questions-table")
            with TabPane("Glossary", id="tab-glossary"):
                yield DataTable(id="glossary-table")
            with TabPane("Risks", id="tab-risks"):
                yield DataTable(id="risks-table")
        yield Footer()

    def on_mount(self) -> None:
        self._load_stakeholders()
        self._load_questions()
        self._load_glossary()
        self._load_risks()

    def _load_stakeholders(self) -> None:
        from praxis.engagement.repos.stakeholders import StakeholderRepo

        table = self.query_one("#stakeholders-table", DataTable)
        table.add_columns("ID", "Name", "Role", "Contact")
        repo = StakeholderRepo(self._engagement_path)
        for s in repo.list_all():
            table.add_row(s.id, s.name, s.role, s.contact_preference.value)

    def _load_questions(self) -> None:
        from praxis.engagement.repos.questions import OpenQuestionsRepo

        table = self.query_one("#questions-table", DataTable)
        table.add_columns("ID", "Status", "Priority", "Question")
        repo = OpenQuestionsRepo(self._engagement_path)
        for q in repo.list_all():
            table.add_row(q.id, q.status, q.priority, q.question[:60])

    def _load_glossary(self) -> None:
        from praxis.engagement.repos.glossary import GlossaryRepo

        table = self.query_one("#glossary-table", DataTable)
        table.add_columns("Term", "Definition")
        repo = GlossaryRepo(self._engagement_path)
        for entry in repo.load().terms:
            table.add_row(entry.term, entry.definition[:80])

    def _load_risks(self) -> None:
        from praxis.engagement.repos.risks import RiskRepo

        table = self.query_one("#risks-table", DataTable)
        table.add_columns("ID", "Title", "Likelihood", "Impact")
        repo = RiskRepo(self._engagement_path)
        for r in repo.list_all():
            table.add_row(r.id, r.title, r.likelihood, r.impact)

    def action_refresh(self) -> None:
        for table_id in (
            "#stakeholders-table",
            "#questions-table",
            "#glossary-table",
            "#risks-table",
        ):
            self.query_one(table_id, DataTable).clear()
        self._load_stakeholders()
        self._load_questions()
        self._load_glossary()
        self._load_risks()
