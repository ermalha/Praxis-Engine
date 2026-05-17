"""Integration tests for artifact ↔ sufficiency report auto-binding (D-037).

Closes RW-009. ``ArtifactResult.sufficiency_verdict`` and
``sufficiency_report_path`` were always ``None`` even when a matching
sufficiency report existed. ``generate_artifact`` now looks up the most
recent matching report (mapping: ``scope-brief↔spec``) and populates
both fields.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from praxis.artifacts.service import generate_artifact
from praxis.config.engagement import init_engagement
from praxis.config.models import ModelConfig, ProfileConfig, Provider
from praxis.transport import ChatRequest, ChatResponse


class _FakeTransport:
    name = "fake"

    def __init__(self, content: str = "stub artifact content") -> None:
        self._content = content

    def chat(self, _request: ChatRequest) -> ChatResponse:
        return ChatResponse(content=self._content, finish_reason="stop")


def _write_sufficiency_report(
    eng: Path,
    *,
    name: str,
    artifact_kind: str,
    verdict: str,
    generated_at: str,
) -> Path:
    reports_dir = eng / ".praxis" / "state" / "sufficiency-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "artifact_kind": artifact_kind,
                "artifact_target": "MVP functional requirements",
                "verdict": verdict,
                "generated_at": generated_at,
            }
        )
    )
    return path


def _stub_profile() -> ProfileConfig:
    return ProfileConfig(
        name="test",
        model_aliases={
            "default": ModelConfig(
                provider=Provider.OPENAI,
                model="gpt-test",
                api_key_env="OPENAI_API_KEY",
            )
        },
        default_model_alias="default",
    )


class TestArtifactSufficiencyBinding:
    def test_scope_brief_binds_to_spec_report(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        report_path = _write_sufficiency_report(
            tmp_engagement,
            name="spec-1",
            artifact_kind="spec",
            verdict="insufficient",
            generated_at="2026-05-17T10:00:00Z",
        )

        result = generate_artifact(
            engagement_path=tmp_engagement,
            profile=_stub_profile(),
            model="gpt-test",
            transport=_FakeTransport(),
            artifact_kind="scope-brief",
            prompt="test",
            output_dir="reports",
        )

        assert result.sufficiency_verdict == "insufficient"
        assert result.sufficiency_report_path == report_path.resolve()

    def test_no_matching_report_yields_null(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        # No sufficiency reports at all.
        result = generate_artifact(
            engagement_path=tmp_engagement,
            profile=_stub_profile(),
            model="gpt-test",
            transport=_FakeTransport(),
            artifact_kind="scope-brief",
            prompt="test",
            output_dir="reports",
        )

        assert result.sufficiency_verdict is None
        assert result.sufficiency_report_path is None

    def test_latest_report_wins_when_multiple(self, tmp_engagement: Path) -> None:
        init_engagement(tmp_engagement, "Test")
        _write_sufficiency_report(
            tmp_engagement,
            name="old",
            artifact_kind="spec",
            verdict="partial",
            generated_at="2026-04-01T10:00:00Z",
        )
        newer_path = _write_sufficiency_report(
            tmp_engagement,
            name="new",
            artifact_kind="spec",
            verdict="insufficient",
            generated_at="2026-05-17T10:00:00Z",
        )

        result = generate_artifact(
            engagement_path=tmp_engagement,
            profile=_stub_profile(),
            model="gpt-test",
            transport=_FakeTransport(),
            artifact_kind="scope-brief",
            prompt="test",
            output_dir="reports",
        )

        assert result.sufficiency_verdict == "insufficient"
        assert result.sufficiency_report_path == newer_path.resolve()

    def test_unrelated_kind_does_not_bind(self, tmp_engagement: Path) -> None:
        """A backlog sufficiency report should NOT bind to a scope-brief artifact."""
        init_engagement(tmp_engagement, "Test")
        _write_sufficiency_report(
            tmp_engagement,
            name="backlog-1",
            artifact_kind="backlog",
            verdict="insufficient",
            generated_at="2026-05-17T10:00:00Z",
        )

        result = generate_artifact(
            engagement_path=tmp_engagement,
            profile=_stub_profile(),
            model="gpt-test",
            transport=_FakeTransport(),
            artifact_kind="scope-brief",
            prompt="test",
            output_dir="reports",
        )

        assert result.sufficiency_verdict is None
        assert result.sufficiency_report_path is None

    def test_used_at(self, tmp_engagement: Path) -> None:
        """Smoke: the created_at field is populated even without binding."""
        init_engagement(tmp_engagement, "Test")
        before = datetime.now(UTC)
        result = generate_artifact(
            engagement_path=tmp_engagement,
            profile=_stub_profile(),
            model="gpt-test",
            transport=_FakeTransport(),
            artifact_kind="scope-brief",
            prompt="test",
            output_dir="reports",
        )
        assert result.created_at >= before
