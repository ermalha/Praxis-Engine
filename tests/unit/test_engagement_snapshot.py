"""D-059 — Unit tests for ``EngagementSnapshot`` + ``render_snapshot_for_llm``.

Beyond proving the new module behaves correctly in isolation, these tests
pin the **byte-for-byte equivalence** between the renderer's output and
the legacy prompt builders. That equivalence is what makes the migration
in D-059's second commit safe: callers' LLM behaviour cannot change
because their prompts haven't.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.engagement.repos import (
    AssumptionsConstraintsRepo,
    DecisionRepo,
    GlossaryRepo,
    OpenQuestionsRepo,
    RiskRepo,
    StakeholderRepo,
)
from praxis.engagement.snapshot import (
    EngagementSnapshot,
    build_engagement_snapshot,
    render_snapshot_for_llm,
)


@pytest.fixture()
def populated_engagement(tmp_engagement: Path, tmp_home: Path) -> Path:
    """An engagement with ≥1 of every entity type so snapshot fields are exercised."""
    init_engagement(tmp_engagement, "Test")

    StakeholderRepo(tmp_engagement).add(name="Alice Chen", role="VP of Lending")
    StakeholderRepo(tmp_engagement).add(name="Devon Price", role="Product Manager")

    GlossaryRepo(tmp_engagement).add_term("Member", "A credit-union customer.")

    DecisionRepo(tmp_engagement).create(
        title="MVP scope: personal loans only",
        context="Sponsor confirmed scope after Q1 review.",
        decision="MVP covers personal loans only. Auto loans deferred.",
        consequences="Backlog sized for personal loans only.",
    )

    ac = AssumptionsConstraintsRepo(tmp_engagement)
    ac.add_constraint(statement="Must comply with GLBA.", constraint_type="regulatory")
    ac.add_assumption(statement="Identity provider supports OIDC.")

    RiskRepo(tmp_engagement).add(
        title="Vendor sandbox delay",
        description="Core banking sandbox needs 2 weeks.",
        impact="medium",
        likelihood="medium",
    )

    OpenQuestionsRepo(tmp_engagement).open(
        question="What is the launch deadline?",
        why_it_matters="Drives all scope choices.",
        priority="critical",
    )
    return tmp_engagement


class TestBuildEngagementSnapshot:
    def test_loads_all_entity_types(self, populated_engagement: Path) -> None:
        snapshot = build_engagement_snapshot(populated_engagement)

        assert isinstance(snapshot, EngagementSnapshot)
        assert snapshot.name == "Test"
        assert len(snapshot.stakeholders) == 2
        assert len(snapshot.glossary_terms) == 1
        assert len(snapshot.decisions) == 1
        assert len(snapshot.constraints) == 1
        assert len(snapshot.assumptions) == 1
        assert len(snapshot.risks) == 1
        assert len(snapshot.open_questions) == 1
        assert snapshot.answered_questions == []

    def test_empty_engagement_yields_empty_lists(
        self, tmp_engagement: Path, tmp_home: Path
    ) -> None:
        init_engagement(tmp_engagement, "Empty")
        snapshot = build_engagement_snapshot(tmp_engagement)

        assert snapshot.stakeholders == []
        assert snapshot.glossary_terms == []
        assert snapshot.decisions == []
        assert snapshot.constraints == []
        assert snapshot.assumptions == []
        assert snapshot.risks == []
        assert snapshot.open_questions == []


class TestRenderForAsk:
    def test_matches_legacy_digest_byte_for_byte(self, populated_engagement: Path) -> None:
        """The new renderer must produce the same text the legacy
        ``build_engagement_digest`` produced — otherwise the migrating
        wrapper would change what the LLM sees."""
        from praxis.engagement.digest import build_engagement_digest

        legacy_name, legacy_text = build_engagement_digest(populated_engagement)

        snapshot = build_engagement_snapshot(populated_engagement)
        new_text = render_snapshot_for_llm(snapshot, purpose="ask")

        assert snapshot.name == legacy_name
        assert new_text == legacy_text, (
            "render_snapshot_for_llm(purpose='ask') drifted from "
            "build_engagement_digest. This would change LLM behaviour for "
            "praxis ask -e ..."
        )

    def test_empty_engagement_yields_none_markers(
        self, tmp_engagement: Path, tmp_home: Path
    ) -> None:
        init_engagement(tmp_engagement, "Empty")
        snapshot = build_engagement_snapshot(tmp_engagement)
        text = render_snapshot_for_llm(snapshot, purpose="ask")

        # All four sections should emit "(none)" rather than be omitted.
        assert text.count("- (none)") == 4


class TestRenderForSufficiency:
    def test_matches_legacy_context_byte_for_byte(self, populated_engagement: Path) -> None:
        from praxis.core.sufficiency import _collect_engagement_context

        legacy = _collect_engagement_context(populated_engagement)
        snapshot = build_engagement_snapshot(populated_engagement)
        new_text = render_snapshot_for_llm(snapshot, purpose="sufficiency")

        # Legacy returns ``str | None``; empty-rendered means no parts.
        if legacy is None:
            assert new_text == ""
        else:
            assert new_text == legacy, (
                "render_snapshot_for_llm(purpose='sufficiency') drifted from "
                "_collect_engagement_context. This would change Sufficiency "
                "Gate prompt construction."
            )

    def test_includes_decision_with_id_citation_instructions(
        self, populated_engagement: Path
    ) -> None:
        """D-038 invariant: decisions are surfaced with the 'cite IDs in have'
        instruction so the gate model can credit decisions."""
        snapshot = build_engagement_snapshot(populated_engagement)
        text = render_snapshot_for_llm(snapshot, purpose="sufficiency")

        assert "Decisions (cite IDs in `have` when they answer a need):" in text
        assert "Constraints (cite IDs in `have` when they bound a need):" in text

    def test_empty_engagement_yields_empty_string(
        self, tmp_engagement: Path, tmp_home: Path
    ) -> None:
        init_engagement(tmp_engagement, "Empty")
        snapshot = build_engagement_snapshot(tmp_engagement)
        assert render_snapshot_for_llm(snapshot, purpose="sufficiency") == ""


class TestRenderForArtifact:
    def test_matches_legacy_build_artifact_prompt_state_section(
        self, populated_engagement: Path
    ) -> None:
        """The artifact renderer produces the **engagement-state portion** of
        the legacy ``build_artifact_prompt`` — without the system header.
        Verify by reconstructing what the wrapper would emit and matching
        the legacy prompt exactly."""
        from praxis.artifacts.service import build_artifact_prompt

        legacy = build_artifact_prompt(populated_engagement, "spec", "test prompt")
        snapshot = build_engagement_snapshot(populated_engagement)
        state = render_snapshot_for_llm(snapshot, purpose="artifact")

        # Reconstruct: state must appear after "Persisted engagement model:\n"
        # in the legacy output.
        assert f"Persisted engagement model:\n{state}\n" in legacy, (
            "Artifact-state renderer output doesn't appear in the legacy "
            "build_artifact_prompt output. The state-only renderer drifted."
        )

    def test_lists_all_entities_without_truncation(self, populated_engagement: Path) -> None:
        """Unlike the ask + sufficiency variants, the artifact renderer
        does not cap or truncate. Long decision bodies / dozens of items
        must surface in full so generated artifacts are complete."""
        snapshot = build_engagement_snapshot(populated_engagement)
        text = render_snapshot_for_llm(snapshot, purpose="artifact")

        # All sections present, even when entity counts are low.
        for header in (
            "Stakeholders:",
            "Glossary:",
            "Questions:",
            "Assumptions:",
            "Constraints:",
            "Risks:",
            "Decisions:",
        ):
            assert header in text


class TestPurposeValidation:
    def test_invalid_purpose_raises(self, populated_engagement: Path) -> None:
        snapshot = build_engagement_snapshot(populated_engagement)
        with pytest.raises(ValueError, match="Unknown purpose"):
            render_snapshot_for_llm(snapshot, purpose="bogus")  # type: ignore[arg-type]
