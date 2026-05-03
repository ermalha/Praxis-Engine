"""Built-in agent tools — session search, file I/O, web fetch, time, sufficiency, wake."""

from __future__ import annotations

from datetime import UTC, datetime

from praxis.errors import ToolError
from praxis.tools.context import ToolContext
from praxis.tools.decorator import tool
from praxis.tools.models import ToolResult


@tool(
    name="current_time",
    description="Return the current UTC date and time.",
    toolset="agent",
)
def current_time(_ctx: ToolContext) -> ToolResult:
    """Return the current UTC datetime."""
    now = datetime.now(UTC)
    return ToolResult(
        content=now.isoformat(),
        data={"utc": now.isoformat()},
    )


@tool(
    name="session_search",
    description="Full-text search across conversation history.",
    toolset="agent",
)
def session_search(ctx: ToolContext, query: str) -> ToolResult:
    """Search past messages using FTS5."""
    if ctx.engagement_path is None:
        return ToolResult(content="No engagement active.", data={"results": []})

    from praxis.storage.repos.messages import MessageRepo

    db_path = ctx.engagement_path / ".praxis" / "state" / "praxis.db"
    repo = MessageRepo(db_path)
    results = repo.fts_search(query, limit=10)

    if not results:
        return ToolResult(
            content=f"No messages match {query!r}.",
            data={"results": []},
        )

    lines = []
    for r in results:
        snippet = r.content[:200]
        lines.append(f"- [{r.role}] {snippet}")

    return ToolResult(
        content="\n".join(lines),
        data={"results": [r.model_dump(mode="json") for r in results]},
    )


@tool(
    name="read_file",
    description="Read a file from the engagement artifacts directory.",
    toolset="agent",
)
def read_file(ctx: ToolContext, path: str) -> ToolResult:
    """Read a file from the engagement workspace.

    Path is relative to ``<engagement>/.praxis/artifacts/``.
    """
    if ctx.engagement_path is None:
        raise ToolError("No engagement active", tool="read_file")

    artifacts_dir = ctx.engagement_path / ".praxis" / "artifacts"
    target = (artifacts_dir / path).resolve()

    # Validate path is within artifacts dir
    if not str(target).startswith(str(artifacts_dir.resolve())):
        raise ToolError(
            f"Path traversal rejected: {path!r}",
            tool="read_file",
            path=path,
        )

    if not target.is_file():
        return ToolResult(
            content=f"File not found: {path}",
            data={"error": "not_found"},
        )

    content = target.read_text(encoding="utf-8")
    return ToolResult(content=content, data={"path": path, "size": len(content)})


@tool(
    name="write_file",
    description="Write a file to the engagement artifacts directory.",
    toolset="agent",
    dangerous=True,
)
def write_file(ctx: ToolContext, path: str, content: str) -> ToolResult:
    """Write a file to the engagement workspace.

    Path is relative to ``<engagement>/.praxis/artifacts/``.
    Rejects path traversal attempts.
    """
    if ctx.engagement_path is None:
        raise ToolError("No engagement active", tool="write_file")

    artifacts_dir = ctx.engagement_path / ".praxis" / "artifacts"
    target = (artifacts_dir / path).resolve()

    # Validate path is within artifacts dir
    if not str(target).startswith(str(artifacts_dir.resolve())):
        raise ToolError(
            f"Path traversal rejected: {path!r}",
            tool="write_file",
            path=path,
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return ToolResult(
        content=f"Wrote {len(content)} bytes to {path}",
        data={"path": path, "size": len(content)},
    )


@tool(
    name="web_fetch",
    description="Fetch content from a URL (basic HTTP GET, no JavaScript).",
    toolset="agent",
)
def web_fetch(_ctx: ToolContext, url: str) -> ToolResult:
    """Fetch a URL and return its text content."""
    import httpx

    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        return ToolResult(
            content=f"HTTP error fetching {url}: {exc}",
            data={"error": str(exc)},
        )

    # Truncate large responses
    text = resp.text
    max_chars = 50_000
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[Truncated at {max_chars} characters]"

    return ToolResult(
        content=text,
        data={"url": url, "status": resp.status_code, "size": len(resp.text)},
    )


@tool(
    name="sufficiency_check",
    description=(
        "Run a sufficiency gate check before producing an artifact. "
        "Evaluates whether enough information is available."
    ),
    toolset="meta",
)
def sufficiency_check(
    ctx: ToolContext,
    artifact_kind: str,
    artifact_target: str,
    extra_context: str | None = None,
) -> ToolResult:
    """Evaluate information sufficiency for an artifact."""
    if ctx.engagement_path is None:
        raise ToolError("No engagement active", tool="sufficiency_check")

    from praxis.config.loader import resolve_model_config
    from praxis.core.sufficiency import run_sufficiency_gate
    from praxis.transport.factory import make_transport

    # Resolve model — prefer sufficiency_gate_model_alias if set
    model_alias = ctx.profile.sufficiency_gate_model_alias
    try:
        model_config = resolve_model_config(ctx.profile, ctx.engagement, model_alias)
        transport = make_transport(model_config)
        model = model_config.model
    except Exception as exc:  # noqa: BLE001
        raise ToolError(
            "Cannot resolve model for sufficiency gate",
            tool="sufficiency_check",
        ) from exc

    report = run_sufficiency_gate(
        artifact_kind,
        artifact_target,
        transport=transport,
        model=model,
        engagement_path=ctx.engagement_path,
        extra_context=extra_context,
    )

    # Format human-readable summary
    lines = [
        f"Sufficiency Check: {report.artifact_kind}",
        f"Target: {report.artifact_target}",
        f"Verdict: {report.verdict.value.upper()}",
        f"Action: {report.recommended_action}",
        "",
        "Information needs:",
    ]
    for need in report.information_needs:
        marker = "x" if need.status == "known" else ("~" if need.status == "partial" else " ")
        blocker_tag = " [BLOCKER]" if need.blocker else ""
        lines.append(f"  [{marker}] {need.need}{blocker_tag}")
        if need.have:
            lines.append(f"      Have: {need.have}")
        if need.missing:
            lines.append(f"      Missing: {need.missing}")

    if report.elicitation_targets:
        lines.append(f"\nElicitation targets: {', '.join(report.elicitation_targets)}")

    lines.append(f"\nReasoning: {report.reasoning}")

    return ToolResult(
        content="\n".join(lines),
        data=report.model_dump(mode="json"),
    )


@tool(
    name="plan_elicitations_for_report",
    description=(
        "Plan elicitation drafts from a sufficiency report. "
        "Produces targeted messages to fill information gaps."
    ),
    toolset="meta",
)
def plan_elicitations_for_report(
    ctx: ToolContext,
    sufficiency_report_id: str,
    max_drafts: int = 5,
) -> ToolResult:
    """Plan elicitations from a persisted sufficiency report."""
    if ctx.engagement_path is None:
        raise ToolError("No engagement active", tool="plan_elicitations_for_report")

    import json as _json

    from praxis.config.loader import resolve_model_config
    from praxis.core.elicitation import plan_elicitations
    from praxis.core.sufficiency import SufficiencyReport
    from praxis.transport.factory import make_transport

    # Load the report from disk
    reports_dir = ctx.engagement_path / ".praxis" / "state" / "sufficiency-reports"
    report_path = reports_dir / f"{sufficiency_report_id}.json"
    if not report_path.is_file():
        # Try matching by prefix
        matches = list(reports_dir.glob(f"{sufficiency_report_id}*.json"))
        if len(matches) == 1:
            report_path = matches[0]
        elif not matches:
            return ToolResult(
                content=f"Report {sufficiency_report_id!r} not found.",
                data={"error": "not_found"},
            )
        else:
            return ToolResult(
                content=f"Ambiguous ID: {len(matches)} matches.",
                data={"error": "ambiguous"},
            )

    report_data = _json.loads(report_path.read_text(encoding="utf-8"))
    report = SufficiencyReport.model_validate(report_data)

    # Resolve transport
    model_alias = ctx.profile.sufficiency_gate_model_alias
    try:
        model_config = resolve_model_config(ctx.profile, ctx.engagement, model_alias)
        transport = make_transport(model_config)
        model = model_config.model
    except Exception as exc:  # noqa: BLE001
        raise ToolError(
            "Cannot resolve model for elicitation planner",
            tool="plan_elicitations_for_report",
        ) from exc

    drafts = plan_elicitations(
        report,
        transport=transport,
        model=model,
        engagement_path=ctx.engagement_path,
        max_drafts=max_drafts,
    )

    if not drafts:
        return ToolResult(
            content="No elicitation drafts needed — no gaps found.",
            data={"drafts": []},
        )

    # Format summary
    lines = [f"Planned {len(drafts)} elicitation draft(s):", ""]
    for i, d in enumerate(drafts, 1):
        lines.append(
            f"{i}. [{d.priority.upper()}] {d.mode} → {d.target_stakeholder_name} via {d.channel}"
        )
        lines.append(f"   Needs: {', '.join(d.related_info_needs[:3])}")
        if d.drafted_subject:
            lines.append(f"   Subject: {d.drafted_subject}")

    return ToolResult(
        content="\n".join(lines),
        data={"drafts": [d.model_dump(mode="json") for d in drafts]},
    )


@tool(
    name="wake_status",
    description="Read the most recent wake-cycle reports for the current engagement.",
    toolset="meta",
)
def wake_status(ctx: ToolContext, count: int = 5) -> ToolResult:
    """Return recent wake reports for self-inspection."""
    if ctx.engagement_path is None:
        raise ToolError("No engagement active", tool="wake_status")

    import json as _json

    reports_dir = ctx.engagement_path / ".praxis" / "state" / "wake-reports"
    if not reports_dir.exists():
        return ToolResult(content="No wake reports yet.", data={"reports": []})

    files = sorted(reports_dir.glob("*.json"), reverse=True)[:count]
    reports = []
    for f in files:
        try:
            reports.append(_json.loads(f.read_text(encoding="utf-8")))
        except (OSError, _json.JSONDecodeError):
            continue

    if not reports:
        return ToolResult(content="No wake reports found.", data={"reports": []})

    lines = [f"Last {len(reports)} wake report(s):", ""]
    for r in reports:
        trigger = r.get("trigger", "?")
        executed = r.get("tasks_executed", [])
        created = r.get("workitems_created", [])
        started = r.get("started_at", "?")
        lines.append(f"- {started} [{trigger}]: {len(executed)} tasks, {len(created)} items")

    return ToolResult(content="\n".join(lines), data={"reports": reports})


@tool(
    name="propose_followup",
    description="Schedule an AGENT_FOLLOW_UP work-item for later execution.",
    toolset="meta",
)
def propose_followup(
    ctx: ToolContext,
    title: str,
    description: str,
    priority: str = "medium",
) -> ToolResult:
    """Create an agent follow-up work-item in the queue."""
    if ctx.engagement_path is None:
        raise ToolError("No engagement active", tool="propose_followup")

    from praxis.workqueue import WorkItemPriority, WorkItemType, WorkQueueRepo

    priority_map = {
        "critical": WorkItemPriority.CRITICAL,
        "high": WorkItemPriority.HIGH,
        "medium": WorkItemPriority.MEDIUM,
        "low": WorkItemPriority.LOW,
    }
    pri = priority_map.get(priority.lower(), WorkItemPriority.MEDIUM)

    repo = WorkQueueRepo(ctx.engagement_path)
    item = repo.enqueue(
        type=WorkItemType.AGENT_FOLLOW_UP,
        assignee="agent",
        title=title,
        description=description,
        priority=pri,
        rationale="Proposed by agent via propose_followup tool",
    )

    return ToolResult(
        content=f"Created follow-up: {item.id} — {item.title}",
        data={"id": item.id, "title": item.title, "priority": pri.value},
    )
