"""Generate SVG screenshots of every Praxis TUI screen.

Drives ``PraxisApp`` via Textual's ``Pilot`` test driver against a seeded
demo engagement, captures one SVG per screen, writes to
``docs/screenshots/``. Reproducible: same seed input → same SVGs.

Usage:
    uv run python scripts/gen_screenshots.py [output_dir]

Default output_dir is ``docs/screenshots/``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from praxis.config.engagement import init_engagement
from praxis.config.models import ModelConfig, Provider
from praxis.config.profiles import create_profile, save_profile
from praxis.engagement.repos import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    GlossaryRepo,
    OpenQuestionsRepo,
    RiskRepo,
    StakeholderRepo,
)
from praxis.tui.app import PraxisApp
from praxis.workqueue.models import WorkItemPriority, WorkItemType
from praxis.workqueue.repo import WorkQueueRepo

# Screens to capture: (binding key, app screen name, output filename)
_SCREENS: list[tuple[str, str, str]] = [
    ("1", "queue", "01-queue.svg"),
    ("2", "conversation", "02-chat.svg"),
    ("3", "engagement", "03-engagement.svg"),
    ("4", "audit", "04-audit.svg"),
    ("5", "backlog", "05-backlog.svg"),
    ("6", "config", "06-config.svg"),
    ("7", "setup", "07-setup.svg"),
    ("8", "priorities", "08-priorities.svg"),
    ("9", "artifact_viewer", "09-artifact-viewer.svg"),
]


def _seed_engagement(eng_path: Path) -> None:
    """Seed a small but representative engagement."""
    init_engagement(eng_path, "Acme Loan Intake (demo)")

    # Stakeholders
    StakeholderRepo(eng_path).add(name="Alice Chen", role="VP of Lending")
    StakeholderRepo(eng_path).add(name="Devon Price", role="Product Manager")
    StakeholderRepo(eng_path).add(name="Priya Nair", role="Loan Operations Manager")
    StakeholderRepo(eng_path).add(name="Sam Rivera", role="Engineering Lead")

    # Glossary
    GlossaryRepo(eng_path).add_term("Member", "A credit-union customer or member.")
    GlossaryRepo(eng_path).add_term("Personal loan", "Unsecured consumer loan product.")
    GlossaryRepo(eng_path).add_term("GLBA", "Gramm-Leach-Bliley Act.")

    # Decisions
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

    # Constraints
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

    # Assumption
    ac_repo.add_assumption(
        statement="Identity provider supports OIDC and meets MVP login requirements."
    )

    # Risks
    RiskRepo(eng_path).add(
        title="Vendor sandbox delay",
        description="Core banking sandbox requires 2-week lead time.",
        impact="medium",
        likelihood="medium",
    )

    # Open questions (one critical so the Priorities screen has signal)
    qrepo = OpenQuestionsRepo(eng_path)
    qrepo.open(
        question="What is the explicit launch deadline?",
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

    # Work items — mix of human and agent so the Queue + Priorities screens have rows
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

    # A sample sufficiency report so the Priorities screen shows an insufficient artifact
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

    # A sample artifact file so the Backlog + Artifact Viewer screens have content
    art_dir = eng_path / ".praxis" / "artifacts" / "reports"
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "scope-brief-demo.md").write_text(
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


def _seed_profile(praxis_home: Path) -> str:
    """Create a demo profile so the Config screen has data to show."""
    profile = create_profile("demo", home=praxis_home)
    profile.model_aliases["default"] = ModelConfig(
        provider=Provider.OPENAI,
        model="gpt-4.1",
        api_key_env="OPENAI_API_KEY",
    )
    profile.default_model_alias = "default"
    save_profile(profile, home=praxis_home)
    return "demo"


async def _capture(eng_path: Path, output_dir: Path) -> None:
    """Pilot the TUI through every screen, save SVGs."""
    app = PraxisApp(engagement_path=eng_path, initial_screen="queue")
    async with app.run_test(size=(132, 40)) as pilot:
        await pilot.pause(0.6)  # let on_mount + first _load_* settle
        for key, screen_name, filename in _SCREENS:
            await pilot.press(key)
            # Give the screen a moment to render + first refresh cycle to populate
            await pilot.pause(0.6)
            out_path = output_dir / filename
            app.save_screenshot(path=str(out_path.parent), filename=out_path.name)
            print(f"  wrote {out_path.name} ({screen_name})")


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    output_dir = Path(argv[1]) if len(argv) > 1 else repo_root / "docs" / "screenshots"
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="praxis-screenshot-") as tmp:
        tmp_path = Path(tmp)
        praxis_home = tmp_path / ".praxis"
        praxis_home.mkdir()
        # Isolate this run from the user's real ~/.praxis
        os.environ["PRAXIS_HOME"] = str(praxis_home)
        os.environ.setdefault("OPENAI_API_KEY", "stub-for-screenshots")

        eng_path = tmp_path / "demo-engagement"
        eng_path.mkdir()

        _seed_profile(praxis_home)
        _seed_engagement(eng_path)

        print(f"Generating screenshots into {output_dir}/")
        asyncio.run(_capture(eng_path, output_dir))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
