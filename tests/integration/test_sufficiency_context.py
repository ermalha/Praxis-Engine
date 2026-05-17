"""Integration tests for the sufficiency gate prompt context (D-038).

Closes RW-004. The sufficiency gate's engagement context previously
listed stakeholders by name + counts of questions/risks — decisions
and constraints were entirely absent. The gate couldn't credit a new
decision against an open information need, so verdicts barely improved
when state was added.

After D-038 the context includes:
  - Full decision bodies (capped 300 chars) with IDs
  - Constraint statements + type
  - Recent assumptions (top 5)
And the system prompt instructs the LLM to consult them first and cite
IDs in ``have``.
"""

from __future__ import annotations

from pathlib import Path

from praxis.config.engagement import init_engagement
from praxis.core.sufficiency import (
    _GATE_SYSTEM_PROMPT,
    _build_gate_prompt,
    _collect_engagement_context,
)
from praxis.engagement.repos import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
)


class TestSufficiencyContext:
    def test_engagement_context_includes_decision_bodies(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        d = DecisionRepo(tmp_engagement).create(
            title="MVP scope: personal loans only",
            context="Sponsor confirmed scope after Q1 review.",
            decision="MVP covers personal loans; auto loans and credit cards out of scope.",
            consequences="Backlog sized for personal loans.",
        )

        context = _collect_engagement_context(tmp_engagement)

        assert context is not None
        # Section header is present
        assert "Decisions" in context
        # Decision ID and title appear
        assert d.id in context
        assert "MVP scope: personal loans only" in context
        # The decision body (not just the title) appears
        assert "auto loans and credit cards out of scope" in context

    def test_engagement_context_includes_constraints(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        c = AssumptionsConstraintsRepo(tmp_engagement).add_constraint(
            statement="Must comply with GLBA and internal security policies",
            constraint_type="regulatory",
        )

        context = _collect_engagement_context(tmp_engagement)

        assert context is not None
        assert "Constraints" in context
        assert c.id in context
        assert "regulatory" in context
        assert "GLBA" in context

    def test_engagement_context_includes_assumptions(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        a = AssumptionsConstraintsRepo(tmp_engagement).add_assumption(
            statement="Identity provider supports OIDC",
            rationale="Confirmed by engineering",
        )

        context = _collect_engagement_context(tmp_engagement)

        assert context is not None
        assert "assumptions" in context.lower()
        assert a.id in context
        assert "OIDC" in context

    def test_gate_system_prompt_instructs_consult_decisions(self) -> None:
        # The new guidance paragraph appears in the system prompt
        assert "FIRST look at the Decisions and Constraints" in _GATE_SYSTEM_PROMPT
        # The cite-IDs guidance is present
        assert "cite the relevant decision/constraint ID(s) in `have`" in _GATE_SYSTEM_PROMPT
        # The schema example shows ID citation
        assert "Answered by ADR-XXXX" in _GATE_SYSTEM_PROMPT

    def test_context_handles_empty_engagement(self, tmp_engagement: Path) -> None:
        """Fresh init: no decisions/constraints/assumptions → context returns None
        (no sections to emit) without raising."""
        init_engagement(tmp_engagement, "Test")
        # Don't add anything beyond init.
        context = _collect_engagement_context(tmp_engagement)
        # Either None or a short string; either way, no crash and no missing-data exception.
        assert context is None or isinstance(context, str)

    def test_decision_body_is_truncated(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        long_body = "x" * 500
        DecisionRepo(tmp_engagement).create(
            title="Long decision",
            context="ctx",
            decision=long_body,
            consequences="conseq",
        )

        context = _collect_engagement_context(tmp_engagement)

        assert context is not None
        # 500-char body should NOT appear verbatim (cap is 300)
        assert long_body not in context
        # Truncation marker is present
        assert "…" in context

    def test_build_gate_prompt_includes_engagement_context(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        d = DecisionRepo(tmp_engagement).create(
            title="Scope decision",
            context="ctx",
            decision="Personal loans only.",
            consequences="conseq",
        )

        eng_context = _collect_engagement_context(tmp_engagement)
        messages = _build_gate_prompt("spec", "MVP requirements", engagement_context=eng_context)
        # System prompt has the new guidance; user message has the decision
        assert messages[0].role == "system"
        assert "FIRST look at the Decisions" in messages[0].content
        assert messages[1].role == "user"
        assert d.id in messages[1].content
        assert "Personal loans only" in messages[1].content
