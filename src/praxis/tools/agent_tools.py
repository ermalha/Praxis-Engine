"""Built-in agent tools — session search, file I/O, web fetch, time."""

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
