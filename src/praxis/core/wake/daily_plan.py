"""Daily plan generator — summarizes engagement state for the human."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import structlog

from praxis.audit import emit
from praxis.engagement.repos.questions import OpenQuestionsRepo
from praxis.workqueue import WorkItemPriority, WorkQueueRepo, prioritize

from .models import DailyPlan

logger = structlog.get_logger()


def generate_daily_plan(engagement_path: Path) -> DailyPlan:
    """Generate a daily plan summarizing current engagement state.

    This is rule-based: no LLM call needed.  It reads the work-queue,
    open questions, and recent wake reports to produce a structured summary.
    """
    now = datetime.now(UTC)
    date_str = now.strftime("%Y-%m-%d")

    # --- Recent activity from wake reports ---
    recent_activity: list[str] = []
    reports_dir = engagement_path / ".praxis" / "state" / "wake-reports"
    if reports_dir.exists():
        report_files = sorted(reports_dir.glob("*.json"), reverse=True)[:5]
        for rf in report_files:
            try:
                data = json.loads(rf.read_text(encoding="utf-8"))
                executed = data.get("tasks_executed", [])
                if executed:
                    recent_activity.append(f"Wake executed: {', '.join(executed)}")
            except (json.JSONDecodeError, OSError):
                continue

    # --- Top work-items for the human ---
    wq_repo = WorkQueueRepo(engagement_path)
    human_items = [i for i in wq_repo.list(limit=100) if i.assignee == "human"]
    active_items = [i for i in human_items if i.status.value in ("queued", "in_progress")]
    ordered = prioritize(active_items, active_only=True)[:5]
    top_workitems = [f"[{i.priority.value.upper()}] {i.title} ({i.status.value})" for i in ordered]

    # --- Open blockers ---
    open_blockers: list[str] = []
    q_repo = OpenQuestionsRepo(engagement_path)
    critical_qs = [
        q for q in q_repo.list_all() if q.status in ("open", "asked") and q.priority == "critical"
    ]
    for q in critical_qs:
        open_blockers.append(f"Question: {q.question}")

    critical_items = [i for i in active_items if i.priority == WorkItemPriority.CRITICAL]
    for ci in critical_items:
        open_blockers.append(f"Work-item: {ci.title}")

    # --- Build summary ---
    parts = [f"Daily plan for {date_str}."]
    if top_workitems:
        parts.append(f"{len(top_workitems)} prioritized items for today.")
    if open_blockers:
        parts.append(f"{len(open_blockers)} open blockers need attention.")
    if not top_workitems and not open_blockers:
        parts.append("No urgent items. Engagement is on track.")

    plan = DailyPlan(
        date=date_str,
        summary=" ".join(parts),
        recent_activity=recent_activity,
        top_workitems=top_workitems,
        open_blockers=open_blockers,
        generated_at=now,
    )

    # Persist
    _persist_daily_plan(engagement_path, plan)

    emit(
        "daily_plan.generated",
        component="orchestrator",
        engagement_path=engagement_path,
        date=date_str,
    )

    return plan


def _persist_daily_plan(engagement_path: Path, plan: DailyPlan) -> None:
    """Save the daily plan as a markdown file."""
    reports_dir = engagement_path / ".praxis" / "artifacts" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = reports_dir / f"daily-plan-{plan.date}.md"

    lines = [
        f"# Daily Plan — {plan.date}",
        "",
        plan.summary,
        "",
    ]

    if plan.top_workitems:
        lines.append("## Top Items")
        lines.append("")
        for item in plan.top_workitems:
            lines.append(f"- {item}")
        lines.append("")

    if plan.open_blockers:
        lines.append("## Blockers")
        lines.append("")
        for b in plan.open_blockers:
            lines.append(f"- {b}")
        lines.append("")

    if plan.recent_activity:
        lines.append("## Recent Activity")
        lines.append("")
        for a in plan.recent_activity:
            lines.append(f"- {a}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
