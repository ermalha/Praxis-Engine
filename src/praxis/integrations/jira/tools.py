"""Jira tools — registered when the Jira integration is enabled."""

from __future__ import annotations

from praxis.tools import ToolContext, ToolResult, tool


@tool(
    name="jira_search_issues",
    description="Search Jira issues using JQL.",
    toolset="jira",
)
def jira_search_issues(ctx: ToolContext, jql: str, limit: int = 20) -> ToolResult:
    """Search Jira issues with a JQL query."""
    from praxis.integrations.jira.client import JiraClient

    client = JiraClient.from_settings(_jira_settings(ctx))
    issues = client.search_issues(jql, limit=limit)
    rows = [{"key": i["key"], "summary": i["fields"].get("summary", "")} for i in issues]
    client.close()
    return ToolResult(
        content="\n".join(f"- {r['key']}: {r['summary']}" for r in rows) or "No issues found.",
        data={"issues": rows},
    )


@tool(
    name="jira_get_issue",
    description="Get a single Jira issue by key.",
    toolset="jira",
)
def jira_get_issue(ctx: ToolContext, key: str) -> ToolResult:
    """Fetch a Jira issue by its key (e.g. BA-42)."""
    from praxis.integrations.jira.client import JiraClient

    client = JiraClient.from_settings(_jira_settings(ctx))
    issue = client.get_issue(key)
    client.close()
    fields = issue.get("fields", {})
    summary = fields.get("summary", "")
    status = fields.get("status", {}).get("name", "Unknown")
    return ToolResult(
        content=f"{issue['key']}: {summary} [{status}]",
        data={"issue": issue},
    )


@tool(
    name="jira_list_projects",
    description="List all accessible Jira projects.",
    toolset="jira",
)
def jira_list_projects(ctx: ToolContext) -> ToolResult:
    """List Jira projects visible to the configured user."""
    from praxis.integrations.jira.client import JiraClient

    client = JiraClient.from_settings(_jira_settings(ctx))
    projects = client.list_projects()
    client.close()
    rows = [{"key": p["key"], "name": p["name"]} for p in projects]
    return ToolResult(
        content="\n".join(f"- {r['key']}: {r['name']}" for r in rows) or "No projects found.",
        data={"projects": rows},
    )


@tool(
    name="jira_get_sprint_issues",
    description="Get issues for a specific sprint.",
    toolset="jira",
)
def jira_get_sprint_issues(ctx: ToolContext, sprint_id: int) -> ToolResult:
    """Fetch issues assigned to a Jira sprint."""
    from praxis.integrations.jira.client import JiraClient

    client = JiraClient.from_settings(_jira_settings(ctx))
    issues = client.get_sprint_issues(sprint_id)
    client.close()
    rows = [{"key": i["key"], "summary": i["fields"].get("summary", "")} for i in issues]
    return ToolResult(
        content="\n".join(f"- {r['key']}: {r['summary']}" for r in rows) or "No issues found.",
        data={"issues": rows},
    )


@tool(
    name="jira_create_issue",
    description="Create a new Jira issue.",
    toolset="jira",
    dangerous=True,
)
def jira_create_issue(
    ctx: ToolContext,
    project: str,
    summary: str,
    description: str,
    issuetype: str = "Story",
) -> ToolResult:
    """Create an issue in Jira. Requires human approval."""
    from praxis.integrations.jira.client import JiraClient

    client = JiraClient.from_settings(_jira_settings(ctx))
    result = client.create_issue(project, summary, description, issuetype)
    client.close()
    key = result.get("key", "unknown")
    return ToolResult(
        content=f"Created issue {key}",
        data={"key": key, "response": result},
    )


@tool(
    name="jira_update_issue",
    description="Update fields on a Jira issue.",
    toolset="jira",
    dangerous=True,
)
def jira_update_issue(
    ctx: ToolContext,
    key: str,
    fields: dict[str, str],
) -> ToolResult:
    """Update an existing Jira issue's fields. Requires human approval."""
    from praxis.integrations.jira.client import JiraClient

    client = JiraClient.from_settings(_jira_settings(ctx))
    client.update_issue(key, fields)
    client.close()
    return ToolResult(content=f"Updated issue {key}")


@tool(
    name="jira_add_comment",
    description="Add a comment to a Jira issue.",
    toolset="jira",
    dangerous=True,
)
def jira_add_comment(ctx: ToolContext, key: str, body: str) -> ToolResult:
    """Add a comment to a Jira issue. Requires human approval."""
    from praxis.integrations.jira.client import JiraClient

    client = JiraClient.from_settings(_jira_settings(ctx))
    result = client.add_comment(key, body)
    client.close()
    return ToolResult(
        content=f"Comment added to {key}",
        data={"comment_id": result.get("id", "")},
    )


@tool(
    name="jira_transition_issue",
    description="Transition a Jira issue to a new status.",
    toolset="jira",
    dangerous=True,
)
def jira_transition_issue(
    ctx: ToolContext,
    key: str,
    transition_id: str,
) -> ToolResult:
    """Transition a Jira issue. Requires human approval."""
    from praxis.integrations.jira.client import JiraClient

    client = JiraClient.from_settings(_jira_settings(ctx))
    client.transition_issue(key, transition_id)
    client.close()
    return ToolResult(content=f"Transitioned issue {key}")


def _jira_settings(ctx: ToolContext) -> dict[str, str]:
    """Extract Jira settings from the engagement config."""
    if ctx.engagement is None:
        return {}
    cfg = ctx.engagement.integrations.get("jira")
    if cfg is None:
        return {}
    return cfg.settings
