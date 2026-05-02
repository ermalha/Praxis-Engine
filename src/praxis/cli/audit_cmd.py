"""``praxis audit`` commands — inspect audit logs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import typer

from praxis.audit import query as audit_query
from praxis.audit import tail as audit_tail
from praxis.config.engagement import find_engagement

audit_app = typer.Typer(name="audit", help="Inspect Praxis audit logs.")

_DEFAULT_HOME = Path.home() / ".praxis"


def _resolve_audit_path(engagement: str | None) -> Path:
    """Resolve the audit JSONL path to read from."""
    if engagement is not None:
        return Path(engagement) / ".praxis" / "state" / "audit.jsonl"

    eng_root = find_engagement(Path.cwd())
    if eng_root is not None:
        return eng_root / ".praxis" / "state" / "audit.jsonl"

    home = Path(os.environ.get("PRAXIS_HOME", str(_DEFAULT_HOME)))
    return home / "audit.jsonl"


@audit_app.command("tail")
def tail(
    n: int = typer.Option(50, "-n", "--lines", help="Number of recent events."),  # noqa: B008
    engagement: str | None = typer.Option(  # noqa: B008
        None, "--engagement", "-e", help="Engagement path."
    ),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON."),  # noqa: B008
) -> None:
    """Show recent audit events."""
    path = _resolve_audit_path(engagement)
    events = audit_tail(path, n=n)
    if not events:
        typer.echo("No audit events found.")
        return
    if as_json:
        typer.echo(json.dumps([e.model_dump(mode="json") for e in events], indent=2, default=str))
    else:
        for ev in events:
            typer.echo(f"[{ev.timestamp}] {ev.event_type} actor={ev.actor} subject={ev.subject_id}")


@audit_app.command("query")
def query(
    event_type: str | None = typer.Option(  # noqa: B008
        None, "--type", "-t", help="Filter by event type."
    ),
    since: str | None = typer.Option(  # noqa: B008
        None, "--since", "-s", help="Events since (ISO 8601)."
    ),
    engagement: str | None = typer.Option(  # noqa: B008
        None, "--engagement", "-e", help="Engagement path."
    ),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON."),  # noqa: B008
) -> None:
    """Query audit events with filters."""
    path = _resolve_audit_path(engagement)
    since_dt = datetime.fromisoformat(since) if since else None
    events = audit_query(path, event_type=event_type, since=since_dt)
    if not events:
        typer.echo("No matching events.")
        return
    if as_json:
        typer.echo(json.dumps([e.model_dump(mode="json") for e in events], indent=2, default=str))
    else:
        for ev in events:
            typer.echo(f"[{ev.timestamp}] {ev.event_type} actor={ev.actor} subject={ev.subject_id}")
