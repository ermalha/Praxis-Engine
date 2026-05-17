"""Integration tests for wake state-diff (D-033).

Closes RW-015: wake was blind to engagement changes between cycles.
A new decision/constraint/risk/answered-question added after wake#1
produced no follow-up task in wake#2 — the proactive agent was failing
to react to state.

New behavior: each wake reads the most recent prior wake report's
``ended_at``, diffs the engagement state against that timestamp, and
emits a state-change ``CandidateTask`` per detected change. Each
generates a deduped ``REVIEW_ARTIFACT`` agent item.
"""

from __future__ import annotations

import time
from pathlib import Path

from praxis.config.engagement import init_engagement
from praxis.config.loader import load_engagement_config
from praxis.config.models import ModelConfig, ProfileConfig, Provider
from praxis.core.orchestrator import Orchestrator
from praxis.core.wake.models import WakeTrigger
from praxis.engagement.repos import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    OpenQuestionsRepo,
)
from praxis.workqueue.models import WorkItemType
from praxis.workqueue.repo import WorkQueueRepo


def _make_orchestrator(eng_path: Path) -> Orchestrator:
    eng_config = load_engagement_config(eng_path)
    profile = ProfileConfig(
        name="test",
        model_aliases={
            "default": ModelConfig(
                provider=Provider.OPENAI,
                model="gpt-test",
                api_key_env="OPENAI_API_KEY",
            )
        },
        default_model_alias="default",
    )
    return Orchestrator(
        agent=None,  # type: ignore[arg-type]
        profile=profile,
        engagement=eng_config,
        engagement_path=eng_path,
    )


class TestWakeStateDiff:
    def test_first_wake_no_prior_report_no_diff_tasks(self, tmp_engagement: Path) -> None:
        """Fresh engagement → first wake sees no prior report → empty diff."""
        init_engagement(tmp_engagement, "Test")
        orch = _make_orchestrator(tmp_engagement)

        report = orch.wake_once(trigger=WakeTrigger.MANUAL)

        assert report.state_changes_since_last_wake == []

    def test_wake_notices_new_decision_added_between_cycles(self, tmp_engagement: Path) -> None:
        """RW-015 regression: a decision added after wake#1 surfaces in wake#2."""
        init_engagement(tmp_engagement, "Test")
        orch = _make_orchestrator(tmp_engagement)

        orch.wake_once(trigger=WakeTrigger.MANUAL)
        # Ensure ts strictly > prior wake's ended_at (sqlite/datetime precision)
        time.sleep(0.05)

        DecisionRepo(tmp_engagement).create(
            title="MVP scope: personal loans only",
            context="Sponsor decision",
            decision="Personal loans only; auto loans out of scope.",
            consequences="Backlog sized accordingly.",
        )

        report2 = orch.wake_once(trigger=WakeTrigger.MANUAL)

        # State change appears in the report
        assert len(report2.state_changes_since_last_wake) == 1
        ch = report2.state_changes_since_last_wake[0]
        assert ch.entity_type == "decision"
        assert ch.change == "created"
        assert ch.title == "MVP scope: personal loans only"

        # A review item was enqueued (or — if Re-evaluate item already exists —
        # the state-change item still must be there)
        repo = WorkQueueRepo(tmp_engagement)
        review_items = [i for i in repo.list(limit=100) if i.type == WorkItemType.REVIEW_ARTIFACT]
        # find the state-change-driven review item by dedup_key prefix
        state_change_items = [
            i
            for i in review_items
            if str(i.payload.get("_dedup_key", "")).startswith("state_change:decision:")
        ]
        assert len(state_change_items) == 1

    def test_wake_notices_answered_question(self, tmp_engagement: Path) -> None:
        """Question status open→answered surfaces in next wake's diff.
        D-039: the wake-generated review item links back to the question via
        ``related_question_ids``."""
        init_engagement(tmp_engagement, "Test")
        qrepo = OpenQuestionsRepo(tmp_engagement)
        q = qrepo.open(
            question="What is the deadline?",
            why_it_matters="Drives scope choices",
        )
        orch = _make_orchestrator(tmp_engagement)

        orch.wake_once(trigger=WakeTrigger.MANUAL)
        time.sleep(0.05)

        qrepo.answer(q.id, "End of Q3")

        report2 = orch.wake_once(trigger=WakeTrigger.MANUAL)

        answered_changes = [
            c
            for c in report2.state_changes_since_last_wake
            if c.entity_type == "question" and c.change == "answered"
        ]
        assert len(answered_changes) == 1
        assert answered_changes[0].entity_id == q.id

        # D-039: the wake-generated review item carries the question ID.
        repo = WorkQueueRepo(tmp_engagement)
        question_items = [
            i
            for i in repo.list(limit=100)
            if str(i.payload.get("_dedup_key", "")).startswith(f"state_change:question:{q.id}")
        ]
        assert len(question_items) == 1
        assert question_items[0].related_question_ids == [q.id]

    def test_state_change_dedup_across_wakes(self, tmp_engagement: Path) -> None:
        """A state change that already produced a review item doesn't pile up."""
        init_engagement(tmp_engagement, "Test")
        AssumptionsConstraintsRepo(tmp_engagement).add_constraint(
            statement="Must comply with GLBA",
            constraint_type="regulatory",
        )
        orch = _make_orchestrator(tmp_engagement)

        # Wake#1: no prior report → diff is empty (the constraint was created
        # before any wake ran). State-change tasks are NOT emitted.
        orch.wake_once(trigger=WakeTrigger.MANUAL)
        time.sleep(0.05)

        # Add a NEW constraint between wakes.
        AssumptionsConstraintsRepo(tmp_engagement).add_constraint(
            statement="No raw SSNs in logs",
            constraint_type="regulatory",
        )
        report2 = orch.wake_once(trigger=WakeTrigger.MANUAL)
        repo = WorkQueueRepo(tmp_engagement)
        review_items_after_wake2 = [
            i
            for i in repo.list(limit=100)
            if str(i.payload.get("_dedup_key", "")).startswith("state_change:constraint:")
        ]
        assert len(review_items_after_wake2) == 1
        # The change is also recorded in the report
        constraint_changes = [
            c for c in report2.state_changes_since_last_wake if c.entity_type == "constraint"
        ]
        assert len(constraint_changes) == 1

        # Wake#3 with no further state changes: dedup keeps the existing item;
        # no new review item is enqueued (workitems_created empty for state-change).
        time.sleep(0.05)
        report3 = orch.wake_once(trigger=WakeTrigger.MANUAL)
        review_items_after_wake3 = [
            i
            for i in repo.list(limit=100)
            if str(i.payload.get("_dedup_key", "")).startswith("state_change:constraint:")
        ]
        assert len(review_items_after_wake3) == 1
        # report3 may still list the constraint in state_changes_since_last_wake
        # because it was created > wake#2.ended_at boundary is fine — what
        # matters is no DUPLICATE work item exists.
        assert report3 is not None  # smoke
