"""EngagementSnapshot — single authoritative read model for engagement state.

Centralizes the repo-reads + LLM-prompt formatting that previously lived in
three+ places (``engagement/digest.py`` for ``ask``,
``core/sufficiency.py:_collect_engagement_context`` for ``check``, and
``artifacts/service.py:build_artifact_prompt`` for ``artifact generate``).

Per Hermes review item #3: "Praxis's core value is 'structured engagement
model as durable memory.' The product should have one authoritative way to
build that memory view." This module is that one place.

Status snapshots + TUI screens still read the repos directly today; they're
queued for a follow-up D-059b migration.

Public surface:

- :class:`EngagementSnapshot` — Pydantic model holding the raw entities.
- :func:`build_engagement_snapshot` — single repo-read pass.
- :func:`render_snapshot_for_llm` — produces the prompt-formatted state
  string for a given ``purpose`` (``"ask"`` / ``"sufficiency"`` /
  ``"artifact"``). Output is byte-for-byte identical to the legacy
  builders so behaviour + prompt-construction tests are unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from praxis.config.loader import load_engagement_config
from praxis.engagement.models import (
    Assumption,
    Constraint,
    Decision,
    GlossaryTerm,
    OpenQuestion,
    Risk,
    Stakeholder,
)
from praxis.engagement.repos import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    GlossaryRepo,
    OpenQuestionsRepo,
    RiskRepo,
    StakeholderRepo,
)

Purpose = Literal["ask", "sufficiency", "artifact"]


# -- Per-purpose formatting constants (preserved from the legacy builders) -

# ``ask`` purpose (engagement/digest.py):
_ASK_DECISION_BODY_LIMIT = 200
_ASK_MAX_DECISIONS = 5
_ASK_MAX_CONSTRAINTS = 7
_ASK_MAX_QUESTIONS = 5
_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# ``sufficiency`` purpose (core/sufficiency.py):
_SUFFICIENCY_DECISION_BODY_LIMIT = 300
_SUFFICIENCY_DECISION_CONTEXT_LIMIT = 150
_SUFFICIENCY_MAX_ASSUMPTIONS = 5


class EngagementSnapshot(BaseModel):
    """Raw structured snapshot of an engagement's state at one point in time."""

    name: str
    methodology: str
    stakeholders: list[Stakeholder]
    glossary_terms: list[GlossaryTerm]
    decisions: list[Decision]
    constraints: list[Constraint]
    assumptions: list[Assumption]
    risks: list[Risk]
    open_questions: list[OpenQuestion]
    answered_questions: list[OpenQuestion]


def build_engagement_snapshot(eng_path: Path) -> EngagementSnapshot:
    """Single repo-read pass — the only place the engagement repos are touched."""
    config = load_engagement_config(eng_path)
    ac_repo = AssumptionsConstraintsRepo(eng_path)
    all_questions = OpenQuestionsRepo(eng_path).list_all()
    methodology = (
        config.methodology.value
        if hasattr(config.methodology, "value")
        else str(config.methodology)
    )
    return EngagementSnapshot(
        name=config.name,
        methodology=methodology,
        stakeholders=StakeholderRepo(eng_path).list_all(),
        glossary_terms=GlossaryRepo(eng_path).load().terms,
        decisions=DecisionRepo(eng_path).list_all(),
        constraints=ac_repo.list_constraints(),
        assumptions=ac_repo.list_assumptions(),
        risks=RiskRepo(eng_path).list_all(),
        open_questions=[q for q in all_questions if q.status == "open"],
        answered_questions=[q for q in all_questions if q.status == "answered"],
    )


def render_snapshot_for_llm(snapshot: EngagementSnapshot, *, purpose: Purpose) -> str:
    """Format the snapshot into a purpose-appropriate LLM-prompt string.

    The output is the *engagement-state portion only* — system instructions /
    user prompts / artifact kind headers stay with the calling site. This
    keeps each consumer's framing distinct while sharing the underlying
    state-rendering.
    """
    if purpose == "ask":
        return _render_for_ask(snapshot)
    if purpose == "sufficiency":
        return _render_for_sufficiency(snapshot)
    if purpose == "artifact":
        return _render_for_artifact(snapshot)
    raise ValueError(f"Unknown purpose: {purpose!r}")


# ---------------------------------------------------------------------------
# ``ask`` rendering — matches engagement/digest.py byte-for-byte.
# ---------------------------------------------------------------------------


def _render_for_ask(s: EngagementSnapshot) -> str:
    lines: list[str] = [f"# Engagement: {s.name}", ""]

    lines.append("## Recent decisions")
    if s.decisions:
        recent = sorted(s.decisions, key=lambda d: d.created_at, reverse=True)[:_ASK_MAX_DECISIONS]
        for d in recent:
            body = d.decision.strip().replace("\n", " ")
            if len(body) > _ASK_DECISION_BODY_LIMIT:
                body = body[: _ASK_DECISION_BODY_LIMIT - 1] + "…"
            lines.append(f"- [{d.id}] {d.title} — {body}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Top constraints")
    if s.constraints:
        for c in s.constraints[:_ASK_MAX_CONSTRAINTS]:
            lines.append(f"- ({c.constraint_type}) {c.statement}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Open questions")
    if s.open_questions:
        sorted_q = sorted(s.open_questions, key=lambda q: _PRIORITY_RANK.get(q.priority, 9))
        for q in sorted_q[:_ASK_MAX_QUESTIONS]:
            lines.append(f"- [{q.priority}] {q.question}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Stakeholders")
    if s.stakeholders:
        for stake in s.stakeholders:
            lines.append(f"- {stake.name} ({stake.role})")
    else:
        lines.append("- (none)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ``sufficiency`` rendering — matches core/sufficiency.py:_collect_engagement_context
# byte-for-byte. Returns an empty string when no entities exist; the legacy
# caller maps "" → None to keep its old contract.
# ---------------------------------------------------------------------------


def _render_for_sufficiency(s: EngagementSnapshot) -> str:
    parts: list[str] = []

    if s.stakeholders:
        lines = ["Known stakeholders:"]
        for stake in s.stakeholders:
            lines.append(f"  - {stake.id}: {stake.name} ({stake.role})")
        parts.append("\n".join(lines))

    if s.decisions:
        sorted_decisions = sorted(s.decisions, key=lambda d: d.created_at, reverse=True)
        lines = ["Decisions (cite IDs in `have` when they answer a need):"]
        for d in sorted_decisions:
            body = d.decision.strip().replace("\n", " ")
            if len(body) > _SUFFICIENCY_DECISION_BODY_LIMIT:
                body = body[: _SUFFICIENCY_DECISION_BODY_LIMIT - 1] + "…"
            ctx = d.context.strip().replace("\n", " ")
            if len(ctx) > _SUFFICIENCY_DECISION_CONTEXT_LIMIT:
                ctx = ctx[: _SUFFICIENCY_DECISION_CONTEXT_LIMIT - 1] + "…"
            lines.append(f"  - [{d.id}] {d.title} — {body} | context: {ctx}")
        parts.append("\n".join(lines))

    if s.constraints:
        lines = ["Constraints (cite IDs in `have` when they bound a need):"]
        for c in s.constraints:
            lines.append(f"  - [{c.id}] ({c.constraint_type}) {c.statement}")
        parts.append("\n".join(lines))

    recent_assumptions = sorted(s.assumptions, key=lambda a: a.created_at, reverse=True)[
        :_SUFFICIENCY_MAX_ASSUMPTIONS
    ]
    if recent_assumptions:
        lines = ["Recent assumptions:"]
        for a in recent_assumptions:
            lines.append(f"  - [{a.id}] {a.statement}")
        parts.append("\n".join(lines))

    if s.glossary_terms:
        parts.append(f"Glossary: {len(s.glossary_terms)} terms defined")

    if s.open_questions:
        parts.append(f"{len(s.open_questions)} open questions")
    if s.risks:
        parts.append(f"{len(s.risks)} risks")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# ``artifact`` rendering — matches artifacts/service.py:build_artifact_prompt
# (the ``state`` portion only — the calling site adds the system header).
# ---------------------------------------------------------------------------


def _render_for_artifact(s: EngagementSnapshot) -> str:
    sections = [
        f"Engagement: {s.name}",
        f"Methodology: {s.methodology}",
        _artifact_stakeholder_section(s),
        _artifact_glossary_section(s),
        _artifact_questions_section(s),
        _artifact_assumptions_constraints_section(s),
        _artifact_risks_section(s),
        _artifact_decisions_section(s),
    ]
    return "\n\n".join(section for section in sections if section.strip())


def _artifact_stakeholder_section(s: EngagementSnapshot) -> str:
    if not s.stakeholders:
        return "Stakeholders: none"
    lines = [f"- {item.name}: {item.role} [{item.id}]" for item in s.stakeholders]
    return "Stakeholders:\n" + "\n".join(lines)


def _artifact_glossary_section(s: EngagementSnapshot) -> str:
    if not s.glossary_terms:
        return "Glossary: none"
    lines = [f"- {term.term}: {term.definition}" for term in s.glossary_terms]
    return "Glossary:\n" + "\n".join(lines)


def _artifact_questions_section(s: EngagementSnapshot) -> str:
    # Legacy: lists ALL questions regardless of status (open + answered + …).
    all_q = list(s.open_questions) + list(s.answered_questions)
    if not all_q:
        return "Questions: none"
    lines = [f"- [{q.status}] {q.question} ({q.priority})" for q in all_q]
    return "Questions:\n" + "\n".join(lines)


def _artifact_assumptions_constraints_section(s: EngagementSnapshot) -> str:
    assumptions = [f"- {item.statement}" for item in s.assumptions]
    constraints = [f"- [{item.constraint_type}] {item.statement}" for item in s.constraints]
    return (
        "Assumptions:\n"
        + ("\n".join(assumptions) if assumptions else "none")
        + "\n\nConstraints:\n"
        + ("\n".join(constraints) if constraints else "none")
    )


def _artifact_risks_section(s: EngagementSnapshot) -> str:
    if not s.risks:
        return "Risks: none"
    lines = [f"- [{r.likelihood}/{r.impact}] {r.title}: {r.description}" for r in s.risks]
    return "Risks:\n" + "\n".join(lines)


def _artifact_decisions_section(s: EngagementSnapshot) -> str:
    if not s.decisions:
        return "Decisions: none"
    lines = [f"- [{d.status}] {d.title}: {d.decision}" for d in s.decisions]
    return "Decisions:\n" + "\n".join(lines)
