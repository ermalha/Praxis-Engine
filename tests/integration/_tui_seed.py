"""Shared seeding helpers for the TUI pilot tests + the screenshot generator.

Extracted from ``scripts/gen_screenshots.py`` so the pilot tests
(``test_tui_pilot.py``) and the screenshot generator use **one source
of truth** for the demo engagement. Drift between the two surfaces
would make screenshots stale relative to tested behaviour.

Public API:

- :func:`seed_demo_engagement` — populate the ``.praxis/`` tree under
  ``eng_path`` with stakeholders / decisions / questions / work-items /
  one sufficiency report / one artifact, sized so the Queue,
  Priorities, Backlog, and Artifact Viewer screens have visible rows.
- :func:`seed_demo_profile` — create a ``demo`` profile bound to gpt-4.1
  via the ``OPENAI_API_KEY`` env var so the Config screen has data.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from praxis.config.engagement import init_engagement
from praxis.config.loader import save_profile
from praxis.config.models import ModelConfig, Provider
from praxis.config.profiles import create_profile
from praxis.engagement.repos import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    GlossaryRepo,
    OpenQuestionsRepo,
    RiskRepo,
    StakeholderRepo,
)
from praxis.workqueue.models import WorkItemPriority, WorkItemType
from praxis.workqueue.repo import WorkQueueRepo

# Stable identifiers tests can assert on without grepping for fuzzy strings.
DEMO_ENGAGEMENT_NAME = "Acme Loan Intake (demo)"
DEMO_PROFILE_NAME = "demo"
DEMO_CRITICAL_QUESTION = "What is the explicit launch deadline?"
DEMO_ARTIFACT_FILENAME = "scope-brief-demo.md"


def seed_demo_engagement(eng_path: Path) -> None:
    """Populate *eng_path*/.praxis/ with a small representative engagement."""
    init_engagement(eng_path, DEMO_ENGAGEMENT_NAME)

    # Stakeholders ------------------------------------------------------
    StakeholderRepo(eng_path).add(name="Alice Chen", role="VP of Lending")
    StakeholderRepo(eng_path).add(name="Devon Price", role="Product Manager")
    StakeholderRepo(eng_path).add(name="Priya Nair", role="Loan Operations Manager")
    StakeholderRepo(eng_path).add(name="Sam Rivera", role="Engineering Lead")

    # Glossary ----------------------------------------------------------
    GlossaryRepo(eng_path).add_term("Member", "A credit-union customer or member.")
    GlossaryRepo(eng_path).add_term("Personal loan", "Unsecured consumer loan product.")
    GlossaryRepo(eng_path).add_term("GLBA", "Gramm-Leach-Bliley Act.")

    # Decisions ---------------------------------------------------------
    DecisionRepo(eng_path).create(
        title="MVP scope: personal loans only",
        context="Sponsor confirmed scope after Q1 review.",
        decision="MVP covers personal loans only. Auto loans deferred.",
        consequences="Backlog sized for personal loans only.",
    )
    DecisionRepo(eng_path).create(
        title="SSN UI masking: last 4 digits",
        context="Compliance Officer requirement.",
        decision="SSN may be entered but is masked to last 4 in UI.",
        consequences="Form/UI must implement masking; log filters required.",
    )

    # Constraints + one assumption -------------------------------------
    ac_repo = AssumptionsConstraintsRepo(eng_path)
    ac_repo.add_constraint(
        statement="Must comply with GLBA and internal security policies.",
        constraint_type="regulatory",
    )
    ac_repo.add_constraint(
        statement="Must launch MVP within 6 months.",
        constraint_type="business",
    )
    ac_repo.add_constraint(statement="Must support mobile browsers.", constraint_type="technical")
    ac_repo.add_assumption(
        statement="Identity provider supports OIDC and meets MVP login requirements."
    )

    # Risks -------------------------------------------------------------
    RiskRepo(eng_path).add(
        title="Vendor sandbox delay",
        description="Core banking sandbox requires 2-week lead time.",
        impact="medium",
        likelihood="medium",
    )

    # Open questions — one CRITICAL so Priorities has signal -----------
    qrepo = OpenQuestionsRepo(eng_path)
    qrepo.open(
        question=DEMO_CRITICAL_QUESTION,
        why_it_matters="Drives all scope choices.",
        priority="critical",
    )
    qrepo.open(
        question="Should partial application progress auto-save across devices?",
        why_it_matters="UX choice with privacy and identity implications.",
        priority="high",
    )
    qrepo.open(
        question="What's our DTI threshold for auto-approval?",
        why_it_matters="Eligibility business rule.",
        priority="medium",
    )

    # Work items — mix of human + agent so the queue/priorities have rows
    wq = WorkQueueRepo(eng_path)
    wq.enqueue(
        type=WorkItemType.CONDUCT_INTERVIEW,
        assignee="human",
        title="Interview Priya: doc requirements by employment type",
        description="Capture salaried vs self-employed document rules.",
        priority=WorkItemPriority.HIGH,
        rationale="Operations gap blocking form design.",
    )
    wq.enqueue(
        type=WorkItemType.SEND_MESSAGE,
        assignee="human",
        title="Follow up on launch deadline (Alice)",
        description="Confirm the executive-committed launch date.",
        priority=WorkItemPriority.CRITICAL,
    )
    wq.enqueue(
        type=WorkItemType.AGENT_FOLLOW_UP,
        assignee="agent",
        title="Elicit drafts for spec: MVP functional requirements",
        description=(
            "Sufficiency check returned INSUFFICIENT. Run `praxis elicit "
            "--latest` to draft stakeholder questions."
        ),
        priority=WorkItemPriority.MEDIUM,
    )

    # Sample sufficiency report so Priorities shows an insufficient artifact
    suff_dir = eng_path / ".praxis" / "state" / "sufficiency-reports"
    suff_dir.mkdir(parents=True, exist_ok=True)
    (suff_dir / "demo-spec.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifact_kind": "spec",
                "artifact_target": "MVP functional requirements for online personal loan flow",
                "information_needs": [],
                "verdict": "insufficient",
                "recommended_action": "elicit",
                "reasoning": "Several blockers remain unanswered.",
                "elicitation_targets": [],
                "generated_at": datetime.now(UTC).isoformat(),
                "by": "agent",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Sample artifact file so Backlog + Artifact Viewer have content
    art_dir = eng_path / ".praxis" / "artifacts" / "reports"
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / DEMO_ARTIFACT_FILENAME).write_text(
        "---\n# Acme Loan Intake — MVP Scope Brief\n\n"
        "## In-scope\n\n"
        "- Online personal loan intake for credit-union members in two pilot branches.\n"
        "- Member login via the existing identity provider (OIDC).\n"
        "- Document upload via the encrypted document service.\n"
        "- Staff work-queue UI showing missing documents, application age, assigned officer.\n\n"
        "## Out-of-scope\n\n"
        "- Auto loans and credit cards.\n"
        "- Core banking platform replacement.\n\n"
        "## Constraints\n\n"
        "- GLBA compliance.\n"
        "- No raw SSN in logs/analytics/exports.\n"
        "- Must launch MVP within 6 months.\n"
        "- Must support mobile browsers.\n\n"
        "## Open questions\n\n"
        "- Explicit launch deadline.\n"
        "- Save-and-resume behavior.\n"
        "- DTI auto-approval threshold.\n\n"
        "_Generated from the persisted Acme Loan Intake engagement model._\n",
        encoding="utf-8",
    )


def seed_demo_profile(praxis_home: Path | None = None) -> str:
    """Create the ``demo`` profile so the Config screen has data to show.

    Pass *praxis_home* explicitly when running outside a ``PRAXIS_HOME``-
    aware fixture (e.g. the screenshot generator's temp dir). When
    ``None``, the helpers fall back to ``$PRAXIS_HOME`` — the test
    fixtures' ``tmp_home`` sets that for us.
    """
    profile = create_profile(DEMO_PROFILE_NAME, home=praxis_home)
    profile.model_aliases["default"] = ModelConfig(
        provider=Provider.OPENAI,
        model="gpt-4.1",
        api_key_env="OPENAI_API_KEY",
    )
    profile.default_model_alias = "default"
    save_profile(profile, home=praxis_home)
    return DEMO_PROFILE_NAME
