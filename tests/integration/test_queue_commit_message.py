"""Integration test: queue commit --message as alias for --note (D-042).

Closes RW-014. The plan §14.2 used --message informally; the CLI only
accepted --note. Now --message and -m are aliases for --note / -n.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.workqueue.models import WorkItemPriority, WorkItemStatus, WorkItemType
from praxis.workqueue.repo import WorkQueueRepo

runner = CliRunner()


class TestQueueCommitMessageAlias:
    def test_commit_with_message_alias_succeeds_and_records_note(
        self, tmp_engagement: Path
    ) -> None:
        init_engagement(tmp_engagement, "Test")
        item = WorkQueueRepo(tmp_engagement).enqueue(
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="human",
            title="Test item",
            description="x",
            priority=WorkItemPriority.MEDIUM,
        )

        result = runner.invoke(
            app,
            [
                "queue",
                "commit",
                item.id,
                "--message",
                "Resolved by the test",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.output
        # The item is now DONE and the note was recorded.
        committed = WorkQueueRepo(tmp_engagement).get(item.id)
        assert committed is not None
        assert committed.status == WorkItemStatus.DONE
        assert committed.completion_note == "Resolved by the test"

    def test_commit_with_short_m_alias_succeeds(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        item = WorkQueueRepo(tmp_engagement).enqueue(
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="human",
            title="Test item",
            description="x",
            priority=WorkItemPriority.MEDIUM,
        )

        result = runner.invoke(
            app,
            [
                "queue",
                "commit",
                item.id,
                "-m",
                "Quick note",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.output
        committed = WorkQueueRepo(tmp_engagement).get(item.id)
        assert committed is not None
        assert committed.completion_note == "Quick note"

    def test_commit_with_legacy_note_flag_still_works(self, tmp_engagement: Path) -> None:
        """Regression: --note and -n keep working."""
        init_engagement(tmp_engagement, "Test")
        item = WorkQueueRepo(tmp_engagement).enqueue(
            type=WorkItemType.AGENT_FOLLOW_UP,
            assignee="human",
            title="Test item",
            description="x",
            priority=WorkItemPriority.MEDIUM,
        )

        result = runner.invoke(
            app,
            [
                "queue",
                "commit",
                item.id,
                "--note",
                "Legacy flag works",
                "-e",
                str(tmp_engagement),
            ],
        )

        assert result.exit_code == 0, result.output
        committed = WorkQueueRepo(tmp_engagement).get(item.id)
        assert committed is not None
        assert committed.completion_note == "Legacy flag works"
