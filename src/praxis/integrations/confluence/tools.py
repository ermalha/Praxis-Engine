"""Confluence tools — registered when the Confluence integration is enabled."""

from __future__ import annotations

from praxis.tools import ToolContext, ToolResult, tool


@tool(
    name="confluence_search",
    description="Search Confluence content using CQL.",
    toolset="confluence",
)
def confluence_search(ctx: ToolContext, cql: str, limit: int = 10) -> ToolResult:
    """Search Confluence pages with a CQL query."""
    from praxis.integrations.confluence.client import ConfluenceClient

    client = ConfluenceClient.from_settings(_confluence_settings(ctx))
    results = client.search(cql, limit=limit)
    client.close()
    rows = [{"id": r.get("id", ""), "title": r.get("title", "")} for r in results]
    return ToolResult(
        content="\n".join(f"- {r['id']}: {r['title']}" for r in rows) or "No results.",
        data={"results": rows},
    )


@tool(
    name="confluence_get_page",
    description="Get a Confluence page by ID or space+title.",
    toolset="confluence",
)
def confluence_get_page(
    ctx: ToolContext,
    space: str | None = None,
    title: str | None = None,
    page_id: str | None = None,
) -> ToolResult:
    """Fetch a Confluence page."""
    from praxis.integrations.confluence.client import ConfluenceClient

    client = ConfluenceClient.from_settings(_confluence_settings(ctx))
    page = client.get_page(space=space, title=title, page_id=page_id)
    client.close()
    page_title = page.get("title", "Untitled")
    body = page.get("body", {}).get("storage", {}).get("value", "")
    return ToolResult(
        content=f"# {page_title}\n\n{body[:2000]}",
        data={"page": page},
    )


@tool(
    name="confluence_create_page",
    description="Create a new Confluence page.",
    toolset="confluence",
    dangerous=True,
)
def confluence_create_page(
    ctx: ToolContext,
    space: str,
    title: str,
    body: str,
    parent_id: str | None = None,
) -> ToolResult:
    """Create a page in Confluence. Requires human approval."""
    from praxis.integrations.confluence.client import ConfluenceClient

    client = ConfluenceClient.from_settings(_confluence_settings(ctx))
    result = client.create_page(space, title, body, parent_id)
    client.close()
    page_id = result.get("id", "unknown")
    return ToolResult(
        content=f"Created page '{title}' (id={page_id})",
        data={"page_id": page_id, "response": result},
    )


@tool(
    name="confluence_update_page",
    description="Update an existing Confluence page.",
    toolset="confluence",
    dangerous=True,
)
def confluence_update_page(
    ctx: ToolContext,
    page_id: str,
    body: str,
    title: str | None = None,
) -> ToolResult:
    """Update a Confluence page's content. Requires human approval."""
    from praxis.integrations.confluence.client import ConfluenceClient

    client = ConfluenceClient.from_settings(_confluence_settings(ctx))
    result = client.update_page(page_id, body, title)
    client.close()
    return ToolResult(
        content=f"Updated page {page_id}",
        data={"response": result},
    )


def _confluence_settings(ctx: ToolContext) -> dict[str, str]:
    """Extract Confluence settings from the engagement config."""
    if ctx.engagement is None:
        return {}
    cfg = ctx.engagement.integrations.get("confluence")
    if cfg is None:
        return {}
    return cfg.settings
