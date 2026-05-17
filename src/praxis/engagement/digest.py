"""Compact engagement-state digest for priming LLM-facing commands.

Used by `praxis ask -e <engagement>` (and any other command that wants a
read-only summary of an engagement) to inject just enough context that the
model can reason about the engagement without hallucinating.
"""

from __future__ import annotations

from pathlib import Path

from praxis.config.loader import load_engagement_config
from praxis.engagement.repos import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    OpenQuestionsRepo,
    StakeholderRepo,
)

_DECISION_BODY_LIMIT = 200
_MAX_DECISIONS = 5
_MAX_CONSTRAINTS = 7
_MAX_QUESTIONS = 5
_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def build_engagement_digest(eng_path: Path) -> tuple[str, str]:
    """Build a compact text digest of an engagement's state.

    Returns ``(engagement_name, digest_text)``. Digest sections:
    header, Recent decisions, Top constraints, Open questions, Stakeholders.
    Decision bodies are truncated at ``_DECISION_BODY_LIMIT`` characters.
    """
    config = load_engagement_config(eng_path)
    decisions = DecisionRepo(eng_path).list_all()
    constraints = AssumptionsConstraintsRepo(eng_path).list_constraints()
    questions = OpenQuestionsRepo(eng_path).list_all(status="open")
    stakeholders = StakeholderRepo(eng_path).list_all()

    lines: list[str] = [f"# Engagement: {config.name}", ""]

    lines.append("## Recent decisions")
    if decisions:
        recent = sorted(decisions, key=lambda d: d.created_at, reverse=True)[:_MAX_DECISIONS]
        for d in recent:
            body = d.decision.strip().replace("\n", " ")
            if len(body) > _DECISION_BODY_LIMIT:
                body = body[: _DECISION_BODY_LIMIT - 1] + "…"
            lines.append(f"- [{d.id}] {d.title} — {body}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Top constraints")
    if constraints:
        for c in constraints[:_MAX_CONSTRAINTS]:
            lines.append(f"- ({c.constraint_type}) {c.statement}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Open questions")
    if questions:
        sorted_q = sorted(questions, key=lambda q: _PRIORITY_RANK.get(q.priority, 9))
        for q in sorted_q[:_MAX_QUESTIONS]:
            lines.append(f"- [{q.priority}] {q.question}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Stakeholders")
    if stakeholders:
        for s in stakeholders:
            lines.append(f"- {s.name} ({s.role})")
    else:
        lines.append("- (none)")

    return config.name, "\n".join(lines)
