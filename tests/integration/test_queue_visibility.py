"""Integration tests for ``praxis queue`` default visibility + assignee filter (D-031).

Closes RW-010: the default queue view filtered to ``assignee=human``, so
items created by wake (always ``assignee=agent``) were invisible — users
saw ``"No work-items."`` after a wake cycle that had actually created
several items.

New behavior: default shows all assignees; ``--assignee {human,agent}``
and ``--human-only`` restore filtering. ``--all`` keeps its status-axis
semantic (include done/rejected items).
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from praxis.cli import app
from praxis.config.engagement import init_engagement
from praxis.workqueue.models import WorkItemPriority, WorkItemStatus, WorkItemType
from praxis.workqueue.repo import WorkQueueRepo

runner = CliRunner()


def _seed_one_human_one_agent(eng: Path) -> tuple[str, str]:
    """Enqueue one human-assigned and one agent-assigned active item.

    Returns (human_id, agent_id).
    """
    repo = WorkQueueRepo(eng)
    h = repo.enqueue(
        type=WorkItemType.REVIEW_ARTIFACT,
        assignee="human",
        title="Human item",
        description="A human-assigned work item.",
        priority=WorkItemPriority.MEDIUM,
    )
    a = repo.enqueue(
        type=WorkItemType.REVIEW_ARTIFACT,
        assignee="agent",
        title="Agent item",
        description="An agent-assigned work item.",
        priority=WorkItemPriority.MEDIUM,
    )
    return h.id, a.id


class TestQueueVisibility:
    def test_default_shows_both_assignees(self, tmp_engagement: Path) -> None:
        """RW-010 regression: default no longer hides agent items."""
        init_engagement(tmp_engagement, "Test")
        _seed_one_human_one_agent(tmp_engagement)

        result = runner.invoke(app, ["queue", "--json", "-e", str(tmp_engagement)])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert len(payload) == 2
        assignees = sorted(i["assignee"] for i in payload)
        assert assignees == ["agent", "human"]

    def test_human_only_filters_agent(self, tmp_engagement: Path) -> None:
        """--human-only restores the pre-D-031 default behavior."""
        init_engagement(tmp_engagement, "Test")
        _seed_one_human_one_agent(tmp_engagement)

        result = runner.invoke(app, ["queue", "--human-only", "--json", "-e", str(tmp_engagement)])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert len(payload) == 1
        assert payload[0]["assignee"] == "human"

    def test_assignee_agent_filter(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        _seed_one_human_one_agent(tmp_engagement)

        result = runner.invoke(
            app,
            ["queue", "--assignee", "agent", "--json", "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert len(payload) == 1
        assert payload[0]["assignee"] == "agent"

    def test_assignee_human_filter(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        _seed_one_human_one_agent(tmp_engagement)

        result = runner.invoke(
            app,
            ["queue", "--assignee", "human", "--json", "-e", str(tmp_engagement)],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert len(payload) == 1
        assert payload[0]["assignee"] == "human"

    def test_all_flag_includes_done_items(self, tmp_engagement: Path) -> None:
        """--all preserves its status-axis semantic: include done items too."""
        init_engagement(tmp_engagement, "Test")
        repo = WorkQueueRepo(tmp_engagement)
        active = repo.enqueue(
            type=WorkItemType.REVIEW_ARTIFACT,
            assignee="human",
            title="Active item",
            description="x",
            priority=WorkItemPriority.MEDIUM,
        )
        done = repo.enqueue(
            type=WorkItemType.REVIEW_ARTIFACT,
            assignee="human",
            title="Done item",
            description="x",
            priority=WorkItemPriority.MEDIUM,
        )
        repo.transition(done.id, WorkItemStatus.IN_PROGRESS)
        repo.transition(done.id, WorkItemStatus.DONE, note="closed")

        # Default (no --all): only the active item
        result_default = runner.invoke(app, ["queue", "--json", "-e", str(tmp_engagement)])
        assert result_default.exit_code == 0, result_default.output
        default_payload = json.loads(result_default.output)
        default_ids = {i["id"] for i in default_payload}
        assert active.id in default_ids
        assert done.id not in default_ids

        # With --all: both
        result_all = runner.invoke(app, ["queue", "--all", "--json", "-e", str(tmp_engagement)])
        assert result_all.exit_code == 0, result_all.output
        all_payload = json.loads(result_all.output)
        all_ids = {i["id"] for i in all_payload}
        assert active.id in all_ids
        assert done.id in all_ids

    def test_invalid_assignee_value_errors_cleanly(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        result = runner.invoke(
            app,
            ["queue", "--assignee", "bogus", "-e", str(tmp_engagement)],
        )
        assert result.exit_code == 1
        combined = result.output + (result.stderr if result.stderr else "")
        assert "Invalid --assignee value" in combined
        assert "Traceback" not in combined
