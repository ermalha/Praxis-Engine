"""Engagement model tools — registered into the chunk-5 tool registry."""

from __future__ import annotations

from praxis.tools import ToolContext, ToolResult, tool

from .repos.assumptions import AssumptionsConstraintsRepo
from .repos.decisions import DecisionRepo
from .repos.glossary import GlossaryRepo
from .repos.questions import OpenQuestionsRepo
from .repos.risks import RiskRepo
from .repos.stakeholders import StakeholderRepo
from .repos.systems import SystemLandscapeRepo
from .repos.timeline import TimelineRepo


def _require_engagement(ctx: ToolContext) -> None:
    """Raise if no engagement is active."""
    if ctx.engagement_path is None:
        msg = "No engagement active"
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# Glossary tools
# ---------------------------------------------------------------------------


@tool(
    name="glossary_search",
    description="Search the engagement glossary for a term or definition.",
    toolset="engagement",
)
def glossary_search(ctx: ToolContext, query: str) -> ToolResult:
    """Case-insensitive substring search on terms and synonyms."""
    _require_engagement(ctx)
    repo = GlossaryRepo(ctx.engagement_path)  # type: ignore[arg-type]
    matches = repo.find(query)
    if not matches:
        return ToolResult(content=f"No glossary terms match {query!r}.", data={"matches": []})
    lines = [f"- **{t.term}**: {t.definition}" for t in matches]
    return ToolResult(content="\n".join(lines), data={"matches": [t.term for t in matches]})


@tool(
    name="glossary_get",
    description="Get a specific glossary term.",
    toolset="engagement",
)
def glossary_get(ctx: ToolContext, term: str) -> ToolResult:
    """Look up a term by exact name."""
    _require_engagement(ctx)
    repo = GlossaryRepo(ctx.engagement_path)  # type: ignore[arg-type]
    t = repo.get(term)
    if t is None:
        return ToolResult(content=f"Term {term!r} not found.", data={"error": "not_found"})
    return ToolResult(
        content=f"**{t.term}**: {t.definition}",
        data=t.model_dump(mode="json"),
    )


@tool(
    name="glossary_add_term",
    description="Add a term to the engagement glossary.",
    toolset="engagement",
    dangerous=True,
)
def glossary_add_term(
    ctx: ToolContext,
    term: str,
    definition: str,
    synonyms: list[str] | None = None,
    notes: str | None = None,
) -> ToolResult:
    """Add a new glossary term."""
    _require_engagement(ctx)
    repo = GlossaryRepo(ctx.engagement_path)  # type: ignore[arg-type]
    t = repo.add_term(term, definition, synonyms=synonyms, notes=notes)
    return ToolResult(content=f"Added term {t.term!r}.", data={"term": t.term})


# ---------------------------------------------------------------------------
# Stakeholder tools
# ---------------------------------------------------------------------------


@tool(
    name="stakeholder_list",
    description="List all stakeholders in the engagement.",
    toolset="engagement",
)
def stakeholder_list(ctx: ToolContext) -> ToolResult:
    """List all stakeholders."""
    _require_engagement(ctx)
    repo = StakeholderRepo(ctx.engagement_path)  # type: ignore[arg-type]
    slist = repo.list_all()
    if not slist:
        return ToolResult(content="No stakeholders.", data={"stakeholders": []})
    lines = [f"- **{s.name}** ({s.role}) [{s.id}]" for s in slist]
    data = [{"id": s.id, "name": s.name, "role": s.role} for s in slist]
    return ToolResult(content="\n".join(lines), data={"stakeholders": data})


@tool(
    name="stakeholder_get",
    description="Get a stakeholder by ID.",
    toolset="engagement",
)
def stakeholder_get(ctx: ToolContext, stakeholder_id: str) -> ToolResult:
    """Look up a stakeholder."""
    _require_engagement(ctx)
    repo = StakeholderRepo(ctx.engagement_path)  # type: ignore[arg-type]
    s = repo.get(stakeholder_id)
    if s is None:
        return ToolResult(
            content=f"Stakeholder {stakeholder_id!r} not found.",
            data={"error": "not_found"},
        )
    return ToolResult(
        content=f"**{s.name}** — {s.role}",
        data=s.model_dump(mode="json"),
    )


@tool(
    name="stakeholder_add",
    description="Add a stakeholder to the engagement.",
    toolset="engagement",
    dangerous=True,
)
def stakeholder_add(
    ctx: ToolContext,
    name: str,
    role: str,
    expertise: list[str] | None = None,
    decision_authority: list[str] | None = None,
) -> ToolResult:
    """Add a new stakeholder."""
    _require_engagement(ctx)
    repo = StakeholderRepo(ctx.engagement_path)  # type: ignore[arg-type]
    s = repo.add(name, role, expertise=expertise, decision_authority=decision_authority)
    return ToolResult(content=f"Added stakeholder {s.name!r} [{s.id}].", data={"id": s.id})


# ---------------------------------------------------------------------------
# Decision tools
# ---------------------------------------------------------------------------


@tool(
    name="decision_list",
    description="List all Architecture Decision Records.",
    toolset="engagement",
)
def decision_list(ctx: ToolContext) -> ToolResult:
    """List all ADRs."""
    _require_engagement(ctx)
    repo = DecisionRepo(ctx.engagement_path)  # type: ignore[arg-type]
    dlist = repo.list_all()
    if not dlist:
        return ToolResult(content="No decisions recorded.", data={"decisions": []})
    lines = [f"- [{d.status}] **{d.title}** ({d.id})" for d in dlist]
    data = [{"id": d.id, "title": d.title, "status": d.status} for d in dlist]
    return ToolResult(content="\n".join(lines), data={"decisions": data})


@tool(
    name="decision_show",
    description="Show a decision record (ADR) by ID.",
    toolset="engagement",
)
def decision_show(ctx: ToolContext, decision_id: str) -> ToolResult:
    """Read a full ADR."""
    _require_engagement(ctx)
    repo = DecisionRepo(ctx.engagement_path)  # type: ignore[arg-type]
    result = repo.get(decision_id)
    if result is None:
        return ToolResult(
            content=f"Decision {decision_id!r} not found.",
            data={"error": "not_found"},
        )
    fm, body = result
    return ToolResult(content=f"# {fm.title}\n\n{body}", data=fm.model_dump(mode="json"))


@tool(
    name="decision_create",
    description="Create a new Architecture Decision Record.",
    toolset="engagement",
    dangerous=True,
)
def decision_create(
    ctx: ToolContext,
    title: str,
    context: str,
    decision: str,
    consequences: str,
    decided_by: list[str] | None = None,
) -> ToolResult:
    """Create a new ADR."""
    _require_engagement(ctx)
    repo = DecisionRepo(ctx.engagement_path)  # type: ignore[arg-type]
    d = repo.create(title, context, decision, consequences, decided_by=decided_by)
    return ToolResult(content=f"Created decision {d.id}.", data={"id": d.id})


# ---------------------------------------------------------------------------
# Question tools
# ---------------------------------------------------------------------------


@tool(
    name="question_list",
    description="List open questions.",
    toolset="engagement",
)
def question_list(ctx: ToolContext, status: str | None = None) -> ToolResult:
    """List questions, optionally filtered by status."""
    _require_engagement(ctx)
    repo = OpenQuestionsRepo(ctx.engagement_path)  # type: ignore[arg-type]
    qlist = repo.list_all(status=status)
    if not qlist:
        return ToolResult(content="No questions.", data={"questions": []})
    lines = [f"- [{q.status}] {q.question} ({q.id})" for q in qlist]
    data = [{"id": q.id, "question": q.question, "status": q.status} for q in qlist]
    return ToolResult(content="\n".join(lines), data={"questions": data})


@tool(
    name="question_open",
    description="Open a new tracked question.",
    toolset="engagement",
    dangerous=True,
)
def question_open(
    ctx: ToolContext,
    question: str,
    why_it_matters: str,
    candidate_answerers: list[str] | None = None,
    priority: str = "medium",
) -> ToolResult:
    """Open a new question."""
    _require_engagement(ctx)
    repo = OpenQuestionsRepo(ctx.engagement_path)  # type: ignore[arg-type]
    q = repo.open(
        question,
        why_it_matters,
        candidate_answerers=candidate_answerers,
        priority=priority,
    )
    return ToolResult(content=f"Opened question {q.id}.", data={"id": q.id})


@tool(
    name="question_answer",
    description="Record an answer to an open question.",
    toolset="engagement",
    dangerous=True,
)
def question_answer(ctx: ToolContext, question_id: str, answer: str) -> ToolResult:
    """Answer a question."""
    _require_engagement(ctx)
    repo = OpenQuestionsRepo(ctx.engagement_path)  # type: ignore[arg-type]
    q = repo.answer(question_id, answer)
    return ToolResult(content=f"Answered question {q.id}.", data={"id": q.id})


# ---------------------------------------------------------------------------
# System tools
# ---------------------------------------------------------------------------


@tool(
    name="system_list",
    description="List systems in the technology landscape.",
    toolset="engagement",
)
def system_list(ctx: ToolContext) -> ToolResult:
    """List all systems."""
    _require_engagement(ctx)
    repo = SystemLandscapeRepo(ctx.engagement_path)  # type: ignore[arg-type]
    slist = repo.list_all()
    if not slist:
        return ToolResult(content="No systems.", data={"systems": []})
    lines = [f"- **{s.name}** ({s.kind}) [{s.id}]" for s in slist]
    data = [{"id": s.id, "name": s.name, "kind": s.kind} for s in slist]
    return ToolResult(content="\n".join(lines), data={"systems": data})


@tool(
    name="system_add",
    description="Add a system to the technology landscape.",
    toolset="engagement",
    dangerous=True,
)
def system_add(
    ctx: ToolContext,
    name: str,
    kind: str,
    description: str | None = None,
) -> ToolResult:
    """Add a system."""
    _require_engagement(ctx)
    repo = SystemLandscapeRepo(ctx.engagement_path)  # type: ignore[arg-type]
    s = repo.add(name, kind, description=description)
    return ToolResult(content=f"Added system {s.name!r} [{s.id}].", data={"id": s.id})


# ---------------------------------------------------------------------------
# Risk tools
# ---------------------------------------------------------------------------


@tool(
    name="risk_list",
    description="List project risks.",
    toolset="engagement",
)
def risk_list(ctx: ToolContext) -> ToolResult:
    """List all risks."""
    _require_engagement(ctx)
    repo = RiskRepo(ctx.engagement_path)  # type: ignore[arg-type]
    rlist = repo.list_all()
    if not rlist:
        return ToolResult(content="No risks.", data={"risks": []})
    lines = [
        f"- [{r.status}] **{r.title}** (L:{r.likelihood} I:{r.impact}) [{r.id}]" for r in rlist
    ]
    data = [{"id": r.id, "title": r.title, "status": r.status} for r in rlist]
    return ToolResult(content="\n".join(lines), data={"risks": data})


@tool(
    name="risk_add",
    description="Add a risk to the register.",
    toolset="engagement",
    dangerous=True,
)
def risk_add(
    ctx: ToolContext,
    title: str,
    description: str,
    likelihood: str,
    impact: str,
    mitigation: str | None = None,
) -> ToolResult:
    """Add a new risk."""
    _require_engagement(ctx)
    repo = RiskRepo(ctx.engagement_path)  # type: ignore[arg-type]
    r = repo.add(title, description, likelihood, impact, mitigation=mitigation)
    return ToolResult(content=f"Added risk {r.title!r} [{r.id}].", data={"id": r.id})


# ---------------------------------------------------------------------------
# Assumption / Constraint tools
# ---------------------------------------------------------------------------


@tool(
    name="assumption_add",
    description="Add a project assumption.",
    toolset="engagement",
    dangerous=True,
)
def assumption_add(
    ctx: ToolContext,
    statement: str,
    rationale: str | None = None,
) -> ToolResult:
    """Add an assumption."""
    _require_engagement(ctx)
    repo = AssumptionsConstraintsRepo(ctx.engagement_path)  # type: ignore[arg-type]
    a = repo.add_assumption(statement, rationale=rationale)
    return ToolResult(content=f"Added assumption [{a.id}].", data={"id": a.id})


@tool(
    name="constraint_add",
    description="Add a project constraint.",
    toolset="engagement",
    dangerous=True,
)
def constraint_add(
    ctx: ToolContext,
    statement: str,
    constraint_type: str,
    source: str | None = None,
) -> ToolResult:
    """Add a constraint."""
    _require_engagement(ctx)
    repo = AssumptionsConstraintsRepo(ctx.engagement_path)  # type: ignore[arg-type]
    c = repo.add_constraint(statement, constraint_type, source=source)
    return ToolResult(content=f"Added constraint [{c.id}].", data={"id": c.id})


# ---------------------------------------------------------------------------
# Timeline tools
# ---------------------------------------------------------------------------


@tool(
    name="milestone_list",
    description="List project milestones.",
    toolset="engagement",
)
def milestone_list(ctx: ToolContext) -> ToolResult:
    """List all milestones."""
    _require_engagement(ctx)
    repo = TimelineRepo(ctx.engagement_path)  # type: ignore[arg-type]
    mlist = repo.list_all()
    if not mlist:
        return ToolResult(content="No milestones.", data={"milestones": []})
    lines = [f"- [{m.status}] **{m.title}** ({m.target_date}) [{m.id}]" for m in mlist]
    data = [{"id": m.id, "title": m.title, "status": m.status} for m in mlist]
    return ToolResult(content="\n".join(lines), data={"milestones": data})


@tool(
    name="milestone_add",
    description="Add a project milestone.",
    toolset="engagement",
    dangerous=True,
)
def milestone_add(
    ctx: ToolContext,
    title: str,
    target_date: str,
    notes: str | None = None,
) -> ToolResult:
    """Add a milestone. target_date format: YYYY-MM-DD."""
    _require_engagement(ctx)
    from datetime import date

    repo = TimelineRepo(ctx.engagement_path)  # type: ignore[arg-type]
    d = date.fromisoformat(target_date)
    m = repo.add(title, d, notes=notes)
    return ToolResult(content=f"Added milestone {m.title!r} [{m.id}].", data={"id": m.id})
