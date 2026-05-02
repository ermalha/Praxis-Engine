"""Work-queue tools — agent-facing interface for the work queue."""

from __future__ import annotations

from praxis.errors import ToolError
from praxis.tools.context import ToolContext
from praxis.tools.decorator import tool
from praxis.tools.models import ToolResult

from .models import WorkItemPriority, WorkItemStatus, WorkItemType
from .repo import WorkQueueRepo


@tool(
    name="workqueue_enqueue",
    description="Create a new work-item in the queue.",
    toolset="workqueue",
    dangerous=True,
)
def workqueue_enqueue(
    ctx: ToolContext,
    item_type: str,
    assignee: str,
    title: str,
    description: str,
    priority: str = "medium",
    rationale: str = "",
) -> ToolResult:
    """Enqueue a new work-item."""
    if ctx.engagement_path is None:
        raise ToolError("No engagement active", tool="workqueue_enqueue")

    repo = WorkQueueRepo(ctx.engagement_path)
    item = repo.enqueue(
        type=WorkItemType(item_type),
        assignee=assignee,
        title=title,
        description=description,
        priority=WorkItemPriority(priority),
        rationale=rationale,
    )

    return ToolResult(
        content=f"Created work-item {item.id}: {item.title}",
        data={"id": item.id, "status": item.status.value},
    )


@tool(
    name="workqueue_list",
    description="List work-items in the queue.",
    toolset="workqueue",
)
def workqueue_list(
    ctx: ToolContext,
    status: str | None = None,
    assignee: str | None = None,
) -> ToolResult:
    """List work-items, optionally filtered."""
    if ctx.engagement_path is None:
        raise ToolError("No engagement active", tool="workqueue_list")

    repo = WorkQueueRepo(ctx.engagement_path)
    ws = WorkItemStatus(status) if status else None
    items = repo.list(status=ws, assignee=assignee)

    if not items:
        return ToolResult(content="No work-items found.", data={"items": []})

    lines = [f"{len(items)} work-item(s):"]
    for i in items:
        lines.append(
            f"  [{i.priority.value.upper()}] {i.id}: {i.title} ({i.status.value}, {i.assignee})"
        )

    return ToolResult(
        content="\n".join(lines),
        data={"items": [i.model_dump(mode="json") for i in items]},
    )


@tool(
    name="workqueue_transition",
    description="Change the status of a work-item.",
    toolset="workqueue",
    dangerous=True,
)
def workqueue_transition(
    ctx: ToolContext,
    item_id: str,
    to: str,
    note: str | None = None,
) -> ToolResult:
    """Transition a work-item status."""
    if ctx.engagement_path is None:
        raise ToolError("No engagement active", tool="workqueue_transition")

    repo = WorkQueueRepo(ctx.engagement_path)
    target = WorkItemStatus(to)

    try:
        updated = repo.transition(item_id, target, note=note)
    except Exception as exc:
        raise ToolError(str(exc), tool="workqueue_transition") from exc

    return ToolResult(
        content=f"Work-item {item_id} → {updated.status.value}",
        data={"id": item_id, "status": updated.status.value},
    )
