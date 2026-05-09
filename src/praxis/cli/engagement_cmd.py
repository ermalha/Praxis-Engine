"""CLI commands for the engagement model."""

from __future__ import annotations

import contextlib
import json
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape as rich_escape
from rich.table import Table

from praxis.audit.context import set_audit_context
from praxis.cli.errors import handle_praxis_errors
from praxis.config.engagement import find_engagement
from praxis.config.loader import load_engagement_config
from praxis.engagement import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    GlossaryRepo,
    OpenQuestionsRepo,
    RiskRepo,
    StakeholderRepo,
    SystemLandscapeRepo,
    TimelineRepo,
)
from praxis.errors import EngagementError

console = Console()
err_console = Console(stderr=True)


def _resolve_engagement(engagement: str | None) -> Path:
    """Resolve the engagement path from the option or CWD."""
    if engagement is not None:
        p = Path(engagement)
        if not (p / ".praxis").is_dir():
            err_console.print(f"[red]Not an engagement: {p}[/red]")
            raise typer.Exit(1)
        return p

    found = find_engagement(Path.cwd())
    if found is None:
        err_console.print("[red]No engagement found. Use --engagement or cd into one.[/red]")
        raise typer.Exit(1)
    return found


def _audit_ctx(eng: Path) -> contextlib.AbstractContextManager[object]:
    """Return an audit context manager scoped to *eng*."""
    config = load_engagement_config(eng)
    return set_audit_context(engagement=config.name, engagement_path=eng)


# ---------------------------------------------------------------------------
# Top-level engagement group
# ---------------------------------------------------------------------------

engagement_app = typer.Typer(name="engagement", help="Manage the engagement model.")

# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------

glossary_app = typer.Typer(name="glossary", help="Manage the engagement glossary.")
engagement_app.add_typer(glossary_app)


@glossary_app.command("list")
@handle_praxis_errors
def glossary_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all glossary terms."""
    eng = _resolve_engagement(engagement)
    repo = GlossaryRepo(eng)
    glossary = repo.load()

    if json_output:
        data = [t.model_dump(mode="json") for t in glossary.terms]
        console.print_json(json.dumps(data))
        return

    if not glossary.terms:
        console.print("[dim]No glossary terms.[/dim]")
        return

    table = Table(title="Glossary")
    table.add_column("Term", style="bold")
    table.add_column("Definition")
    table.add_column("Synonyms")

    for t in glossary.terms:
        table.add_row(t.term, t.definition, ", ".join(t.synonyms) or "-")
    console.print(table)


@glossary_app.command("get")
@handle_praxis_errors
def glossary_get(
    term: str = typer.Argument(..., help="Term to look up."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Get a specific glossary term."""
    eng = _resolve_engagement(engagement)
    repo = GlossaryRepo(eng)
    t = repo.get(term)
    if t is None:
        err_console.print(f"[red]Term {term!r} not found.[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{t.term}[/bold]: {t.definition}")
    if t.synonyms:
        console.print(f"Synonyms: {', '.join(t.synonyms)}")
    if t.notes:
        console.print(f"Notes: {t.notes}")


@glossary_app.command("search")
@handle_praxis_errors
def glossary_search(
    query: str = typer.Argument(..., help="Search query."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Search glossary terms."""
    eng = _resolve_engagement(engagement)
    repo = GlossaryRepo(eng)
    matches = repo.find(query)
    if not matches:
        console.print(f"[dim]No terms match {query!r}.[/dim]")
        return
    for t in matches:
        console.print(f"- [bold]{t.term}[/bold]: {t.definition}")


@glossary_app.command("add")
@handle_praxis_errors
def glossary_add(
    term: str = typer.Argument(..., help="Term name."),
    definition: str = typer.Argument(..., help="Term definition."),
    synonyms: str | None = typer.Option(None, "--synonyms", "-s", help="Comma-separated."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a glossary term."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = GlossaryRepo(eng)
        syn = [s.strip() for s in synonyms.split(",")] if synonyms else None
        try:
            t = repo.add_term(term, definition, synonyms=syn)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Added term {t.term!r}.[/green]")


@glossary_app.command("remove")
@handle_praxis_errors
def glossary_remove(
    term: str = typer.Argument(..., help="Term to remove."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Remove a glossary term."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = GlossaryRepo(eng)
        try:
            repo.remove_term(term)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Removed term {term!r}.[/green]")


# ---------------------------------------------------------------------------
# Stakeholders
# ---------------------------------------------------------------------------

stakeholder_app = typer.Typer(name="stakeholder", help="Manage stakeholders.")
engagement_app.add_typer(stakeholder_app)


@stakeholder_app.command("list")
@handle_praxis_errors
def stakeholder_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all stakeholders."""
    eng = _resolve_engagement(engagement)
    repo = StakeholderRepo(eng)
    slist = repo.list_all()

    if json_output:
        data = [s.model_dump(mode="json") for s in slist]
        console.print_json(json.dumps(data))
        return

    if not slist:
        console.print("[dim]No stakeholders.[/dim]")
        return

    table = Table(title="Stakeholders")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Role")
    table.add_column("Influence")
    table.add_column("Interest")

    for s in slist:
        table.add_row(s.id, s.name, s.role, s.influence, s.interest)
    console.print(table)


@stakeholder_app.command("get")
@handle_praxis_errors
def stakeholder_get(
    sid: str = typer.Argument(..., help="Stakeholder ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Get a stakeholder by ID."""
    eng = _resolve_engagement(engagement)
    repo = StakeholderRepo(eng)
    s = repo.get(sid)
    if s is None:
        err_console.print(f"[red]Stakeholder {sid!r} not found.[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{s.name}[/bold] — {s.role} {rich_escape(f'[{s.id}]')}")
    if s.expertise:
        console.print(f"Expertise: {', '.join(s.expertise)}")
    if s.decision_authority:
        console.print(f"Decision authority: {', '.join(s.decision_authority)}")


@stakeholder_app.command("add")
@handle_praxis_errors
def stakeholder_add(
    name: str = typer.Argument(..., help="Stakeholder name."),
    role: str = typer.Argument(..., help="Stakeholder role."),
    expertise: str | None = typer.Option(None, "--expertise", help="Comma-separated."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a stakeholder."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = StakeholderRepo(eng)
        exp = [e.strip() for e in expertise.split(",")] if expertise else None
        s = repo.add(name, role, expertise=exp)
        console.print(f"[green]Added stakeholder {s.name!r} {rich_escape(f'[{s.id}]')}.[/green]")


@stakeholder_app.command("update")
@handle_praxis_errors
def stakeholder_update(
    sid: str = typer.Argument(..., help="Stakeholder ID."),
    role: str | None = typer.Option(None, "--role"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Update a stakeholder."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = StakeholderRepo(eng)
        kwargs: dict[str, object] = {}
        if role is not None:
            kwargs["role"] = role
        if not kwargs:
            err_console.print("[red]No fields to update.[/red]")
            raise typer.Exit(1)
        try:
            s = repo.update(sid, **kwargs)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Updated stakeholder {s.name!r}.[/green]")


@stakeholder_app.command("remove")
@handle_praxis_errors
def stakeholder_remove(
    sid: str = typer.Argument(..., help="Stakeholder ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Remove a stakeholder."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = StakeholderRepo(eng)
        try:
            repo.remove(sid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Removed stakeholder {sid!r}.[/green]")


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

decision_app = typer.Typer(name="decision", help="Manage architecture decisions.")
engagement_app.add_typer(decision_app)


@decision_app.command("list")
@handle_praxis_errors
def decision_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all decisions (ADRs)."""
    eng = _resolve_engagement(engagement)
    repo = DecisionRepo(eng)
    dlist = repo.list_all()

    if json_output:
        data = [d.model_dump(mode="json") for d in dlist]
        console.print_json(json.dumps(data))
        return

    if not dlist:
        console.print("[dim]No decisions recorded.[/dim]")
        return

    table = Table(title="Decisions")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Status")

    for d in dlist:
        table.add_row(d.id, d.title, d.status)
    console.print(table)


@decision_app.command("show")
@handle_praxis_errors
def decision_show(
    did: str = typer.Argument(..., help="Decision ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Show a decision record."""
    eng = _resolve_engagement(engagement)
    repo = DecisionRepo(eng)
    result = repo.get(did)
    if result is None:
        err_console.print(f"[red]Decision {did!r} not found.[/red]")
        raise typer.Exit(1)
    fm, body = result
    console.print(f"[bold]{fm.title}[/bold] ({fm.id}) [{fm.status}]")
    console.print(body)


@decision_app.command("new")
@handle_praxis_errors
def decision_new(
    title: str = typer.Argument(..., help="Decision title."),
    context: str = typer.Option(..., "--context", help="Decision context."),
    decision: str = typer.Option(..., "--decision", help="The decision."),
    consequences: str = typer.Option(..., "--consequences", help="Consequences."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Create a new decision record."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = DecisionRepo(eng)
        try:
            d = repo.create(title, context, decision, consequences)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Created decision {rich_escape(d.id)}.[/green]")


@decision_app.command("supersede")
@handle_praxis_errors
def decision_supersede(
    did: str = typer.Argument(..., help="Decision ID to supersede."),
    by: str = typer.Option(..., "--by", help="Superseding decision ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Mark a decision as superseded."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = DecisionRepo(eng)
        try:
            d = repo.supersede(did, by)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        msg = f"Decision {rich_escape(d.id)} superseded by {rich_escape(by)}."
        console.print(f"[green]{msg}[/green]")


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

question_app = typer.Typer(name="question", help="Manage open questions.")
engagement_app.add_typer(question_app)


@question_app.command("list")
@handle_praxis_errors
def question_list(
    status: str | None = typer.Option(None, "--status", "-s"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List open questions."""
    eng = _resolve_engagement(engagement)
    repo = OpenQuestionsRepo(eng)
    qlist = repo.list_all(status=status)

    if json_output:
        data = [q.model_dump(mode="json") for q in qlist]
        console.print_json(json.dumps(data))
        return

    if not qlist:
        console.print("[dim]No questions.[/dim]")
        return

    table = Table(title="Questions")
    table.add_column("ID", style="dim")
    table.add_column("Question", style="bold")
    table.add_column("Status")
    table.add_column("Priority")

    for q in qlist:
        table.add_row(q.id, q.question, q.status, q.priority)
    console.print(table)


@question_app.command("open")
@handle_praxis_errors
def question_open(
    question: str = typer.Argument(..., help="The question."),
    why: str = typer.Option(..., "--why", help="Why it matters."),
    priority: str = typer.Option("medium", "--priority", "-p"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Open a new tracked question."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = OpenQuestionsRepo(eng)
        try:
            q = repo.open(question, why, priority=priority)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Opened question {rich_escape(q.id)}.[/green]")


@question_app.command("answer")
@handle_praxis_errors
def question_answer(
    qid: str = typer.Argument(..., help="Question ID."),
    answer: str = typer.Argument(..., help="The answer."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Answer a question."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = OpenQuestionsRepo(eng)
        try:
            q = repo.answer(qid, answer)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Answered question {rich_escape(q.id)}.[/green]")


@question_app.command("withdraw")
@handle_praxis_errors
def question_withdraw(
    qid: str = typer.Argument(..., help="Question ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Withdraw a question."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = OpenQuestionsRepo(eng)
        try:
            q = repo.withdraw(qid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Withdrew question {rich_escape(q.id)}.[/green]")


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------

system_app = typer.Typer(name="system", help="Manage the system landscape.")
engagement_app.add_typer(system_app)


@system_app.command("list")
@handle_praxis_errors
def system_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List systems."""
    eng = _resolve_engagement(engagement)
    repo = SystemLandscapeRepo(eng)
    slist = repo.list_all()

    if json_output:
        data = [s.model_dump(mode="json") for s in slist]
        console.print_json(json.dumps(data))
        return

    if not slist:
        console.print("[dim]No systems.[/dim]")
        return

    table = Table(title="Systems")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Kind")
    table.add_column("Status")

    for s in slist:
        table.add_row(s.id, s.name, s.kind, s.status)
    console.print(table)


@system_app.command("add")
@handle_praxis_errors
def system_add(
    name: str = typer.Argument(..., help="System name."),
    kind: str = typer.Argument(..., help="System kind (e.g. web app, API)."),
    description: str | None = typer.Option(None, "--description", "-d"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a system."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = SystemLandscapeRepo(eng)
        s = repo.add(name, kind, description=description)
        console.print(f"[green]Added system {s.name!r} {rich_escape(f'[{s.id}]')}.[/green]")


@system_app.command("show")
@handle_praxis_errors
def system_show(
    sid: str = typer.Argument(..., help="System ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Show a system."""
    eng = _resolve_engagement(engagement)
    repo = SystemLandscapeRepo(eng)
    s = repo.get(sid)
    if s is None:
        err_console.print(f"[red]System {sid!r} not found.[/red]")
        raise typer.Exit(1)
    console.print(f"[bold]{s.name}[/bold] ({s.kind}) {rich_escape(f'[{s.id}]')}")
    if s.description:
        console.print(f"Description: {s.description}")
    console.print(f"Status: {s.status}")


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------

risk_app = typer.Typer(name="risk", help="Manage the risk register.")
engagement_app.add_typer(risk_app)


@risk_app.command("list")
@handle_praxis_errors
def risk_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List risks."""
    eng = _resolve_engagement(engagement)
    repo = RiskRepo(eng)
    rlist = repo.list_all()

    if json_output:
        data = [r.model_dump(mode="json") for r in rlist]
        console.print_json(json.dumps(data))
        return

    if not rlist:
        console.print("[dim]No risks.[/dim]")
        return

    table = Table(title="Risks")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Likelihood")
    table.add_column("Impact")
    table.add_column("Status")

    for r in rlist:
        table.add_row(r.id, r.title, r.likelihood, r.impact, r.status)
    console.print(table)


@risk_app.command("add")
@handle_praxis_errors
def risk_add(
    title: str = typer.Argument(..., help="Risk title."),
    description: str = typer.Argument(..., help="Risk description."),
    likelihood: str = typer.Option(..., "--likelihood", "-l", help="low/medium/high"),
    impact: str = typer.Option(..., "--impact", "-i", help="low/medium/high"),
    mitigation: str | None = typer.Option(None, "--mitigation", "-m"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a risk."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = RiskRepo(eng)
        r = repo.add(title, description, likelihood, impact, mitigation=mitigation)
        console.print(f"[green]Added risk {r.title!r} {rich_escape(f'[{r.id}]')}.[/green]")


@risk_app.command("update")
@handle_praxis_errors
def risk_update(
    rid: str = typer.Argument(..., help="Risk ID."),
    status: str | None = typer.Option(None, "--status"),
    mitigation: str | None = typer.Option(None, "--mitigation"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Update a risk."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = RiskRepo(eng)
        kwargs: dict[str, object] = {}
        if status is not None:
            kwargs["status"] = status
        if mitigation is not None:
            kwargs["mitigation"] = mitigation
        if not kwargs:
            err_console.print("[red]No fields to update.[/red]")
            raise typer.Exit(1)
        try:
            r = repo.update(rid, **kwargs)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Updated risk {r.title!r}.[/green]")


@risk_app.command("close")
@handle_praxis_errors
def risk_close(
    rid: str = typer.Argument(..., help="Risk ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Close a risk."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = RiskRepo(eng)
        try:
            r = repo.close(rid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Closed risk {r.title!r}.[/green]")


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

timeline_app = typer.Typer(name="timeline", help="Manage project milestones.")
engagement_app.add_typer(timeline_app)


@timeline_app.command("list")
@handle_praxis_errors
def timeline_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List milestones."""
    eng = _resolve_engagement(engagement)
    repo = TimelineRepo(eng)
    mlist = repo.list_all()

    if json_output:
        data = [m.model_dump(mode="json") for m in mlist]
        console.print_json(json.dumps(data))
        return

    if not mlist:
        console.print("[dim]No milestones.[/dim]")
        return

    table = Table(title="Timeline")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Target Date")
    table.add_column("Status")

    for m in mlist:
        table.add_row(m.id, m.title, str(m.target_date), m.status)
    console.print(table)


@timeline_app.command("add")
@handle_praxis_errors
def timeline_add(
    title: str = typer.Argument(..., help="Milestone title."),
    target_date: str = typer.Option(..., "--date", "-d", help="Target date (YYYY-MM-DD)."),
    notes: str | None = typer.Option(None, "--notes"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a milestone."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = TimelineRepo(eng)
        d = date.fromisoformat(target_date)
        m = repo.add(title, d, notes=notes)
        console.print(f"[green]Added milestone {m.title!r} {rich_escape(f'[{m.id}]')}.[/green]")


@timeline_app.command("update")
@handle_praxis_errors
def timeline_update(
    mid: str = typer.Argument(..., help="Milestone ID."),
    status: str | None = typer.Option(None, "--status"),
    target_date: str | None = typer.Option(None, "--date", "-d"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Update a milestone."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = TimelineRepo(eng)
        kwargs: dict[str, object] = {}
        if status is not None:
            kwargs["status"] = status
        if target_date is not None:
            kwargs["target_date"] = date.fromisoformat(target_date)
        if not kwargs:
            err_console.print("[red]No fields to update.[/red]")
            raise typer.Exit(1)
        try:
            m = repo.update(mid, **kwargs)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Updated milestone {m.title!r}.[/green]")


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------

assumption_app = typer.Typer(name="assumption", help="Manage assumptions.")
engagement_app.add_typer(assumption_app)


@assumption_app.command("list")
@handle_praxis_errors
def assumption_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all assumptions."""
    eng = _resolve_engagement(engagement)
    repo = AssumptionsConstraintsRepo(eng)
    alist = repo.list_assumptions()

    if json_output:
        data = [a.model_dump(mode="json") for a in alist]
        console.print_json(json.dumps(data))
        return

    if not alist:
        console.print("[dim]No assumptions.[/dim]")
        return

    table = Table(title="Assumptions")
    table.add_column("ID", style="dim")
    table.add_column("Statement", style="bold")
    table.add_column("Validated")

    for a in alist:
        validated = "yes" if a.validated else "no"
        table.add_row(a.id, a.statement, validated)
    console.print(table)


@assumption_app.command("add")
@handle_praxis_errors
def assumption_add(
    statement: str = typer.Argument(..., help="Assumption statement."),
    rationale: str | None = typer.Option(None, "--rationale", "-r"),
    validation_method: str | None = typer.Option(None, "--validation-method"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add an assumption."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        a = repo.add_assumption(statement, rationale=rationale, validation_method=validation_method)
        console.print(f"[green]Added assumption {rich_escape(f'[{a.id}]')}.[/green]")


@assumption_app.command("validate")
@handle_praxis_errors
def assumption_validate(
    aid: str = typer.Argument(..., help="Assumption ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Mark an assumption as validated."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        try:
            a = repo.validate_assumption(aid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Validated assumption {rich_escape(f'[{a.id}]')}.[/green]")


@assumption_app.command("invalidate")
@handle_praxis_errors
def assumption_invalidate(
    aid: str = typer.Argument(..., help="Assumption ID."),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Mark an assumption as invalidated."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        try:
            a = repo.invalidate_assumption(aid)
        except EngagementError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        console.print(f"[green]Invalidated assumption {rich_escape(f'[{a.id}]')}.[/green]")


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

constraint_app = typer.Typer(name="constraint", help="Manage constraints.")
engagement_app.add_typer(constraint_app)


@constraint_app.command("list")
@handle_praxis_errors
def constraint_list(
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List all constraints."""
    eng = _resolve_engagement(engagement)
    repo = AssumptionsConstraintsRepo(eng)
    clist = repo.list_constraints()

    if json_output:
        data = [c.model_dump(mode="json") for c in clist]
        console.print_json(json.dumps(data))
        return

    if not clist:
        console.print("[dim]No constraints.[/dim]")
        return

    table = Table(title="Constraints")
    table.add_column("ID", style="dim")
    table.add_column("Statement", style="bold")
    table.add_column("Type")
    table.add_column("Source")

    for c in clist:
        table.add_row(c.id, c.statement, c.constraint_type, c.source or "-")
    console.print(table)


@constraint_app.command("add")
@handle_praxis_errors
def constraint_add(
    statement: str = typer.Argument(..., help="Constraint statement."),
    constraint_type: str = typer.Argument(..., help="Type (technical, business, regulatory)."),
    source: str | None = typer.Option(None, "--source", "-s"),
    engagement: str | None = typer.Option(None, "--engagement", "-e"),
) -> None:
    """Add a constraint."""
    eng = _resolve_engagement(engagement)
    with _audit_ctx(eng):
        repo = AssumptionsConstraintsRepo(eng)
        c = repo.add_constraint(statement, constraint_type, source=source)
        console.print(f"[green]Added constraint {rich_escape(f'[{c.id}]')}.[/green]")
