"""Sufficiency Gate — typed self-check before artifact production."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

import structlog
from pydantic import BaseModel, ConfigDict

from praxis.audit import emit
from praxis.errors import SufficiencyError
from praxis.transport.base import Transport
from praxis.transport.models import ChatRequest, Message

from .sufficiency_helpers import load_template

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class InfoNeedStatus(StrEnum):
    KNOWN = "known"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class SufficiencyVerdict(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CandidateSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["stakeholder", "artifact", "external", "registry"]
    ref: str
    rationale: str


class InfoNeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    need: str
    status: InfoNeedStatus
    have: str | None = None
    missing: str | None = None
    blocker: bool
    candidate_sources: list[CandidateSource] = []


class SufficiencyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    artifact_kind: str
    artifact_target: str
    information_needs: list[InfoNeed]
    verdict: SufficiencyVerdict
    recommended_action: Literal["produce", "elicit", "produce_with_caveats"]
    reasoning: str
    elicitation_targets: list[str] = []
    generated_at: datetime
    by: Literal["agent", "human"]


# ---------------------------------------------------------------------------
# Sub-prompt construction
# ---------------------------------------------------------------------------

_GATE_SYSTEM_PROMPT = """\
You are a sufficiency assessor. Given an artifact kind and target description, \
evaluate whether there is enough information to produce that artifact well.

You MUST respond with a single JSON object matching this schema:
{
  "artifact_kind": "<kind>",
  "artifact_target": "<target>",
  "information_needs": [
    {
      "need": "<what info is needed>",
      "status": "known" | "partial" | "unknown",
      "have": "Answered by ADR-XXXX-... or constraint-id; brief summary",
      "missing": "<what is still missing, or null>",
      "blocker": true | false,
      "candidate_sources": [
        {"kind": "stakeholder"|"artifact"|"external"|"registry",
         "ref": "<id>", "rationale": "<why>"}
      ]
    }
  ],
  "verdict": "sufficient" | "partial" | "insufficient",
  "recommended_action": "produce" | "elicit" | "produce_with_caveats",
  "reasoning": "<short explanation>",
  "elicitation_targets": ["<stakeholder-id>", ...]
}

When evaluating each information need, FIRST look at the Decisions and \
Constraints in the engagement context. If a decision or constraint directly \
answers a need, set status="known" and cite the relevant decision/constraint \
ID(s) in `have`. If it partially answers, use "partial" and explain what's \
still missing in `missing`. Only use "unknown" when nothing in the engagement \
state addresses the need.

Rules for the verdict:
- "sufficient" — all information needs are KNOWN. recommended_action = "produce".
- "partial" — no blockers are UNKNOWN, but some needs are PARTIAL. \
recommended_action = "produce_with_caveats".
- "insufficient" — at least one blocker is UNKNOWN. recommended_action = "elicit".

Respond ONLY with the JSON object. No markdown fences, no extra text."""


def _build_gate_prompt(
    artifact_kind: str,
    artifact_target: str,
    *,
    engagement_context: str | None = None,
    extra_context: str | None = None,
) -> list[Message]:
    """Build the message list for the sufficiency gate LLM call."""
    user_parts: list[str] = [
        f"Artifact kind: {artifact_kind}",
        f"Target: {artifact_target}",
    ]

    # Include template hints
    template_needs = load_template(artifact_kind)
    if template_needs:
        needs_text = "\n".join(
            f"- {n['need']} (blocker={n.get('blocker', False)})" for n in template_needs
        )
        user_parts.append(
            f"\nPre-identified information needs (use as starting points, "
            f"add or modify as appropriate):\n{needs_text}"
        )

    if engagement_context:
        user_parts.append(f"\nEngagement context:\n{engagement_context}")

    if extra_context:
        user_parts.append(f"\nAdditional context:\n{extra_context}")

    return [
        Message(role="system", content=_GATE_SYSTEM_PROMPT),
        Message(role="user", content="\n\n".join(user_parts)),
    ]


# ---------------------------------------------------------------------------
# Engagement context builder
# ---------------------------------------------------------------------------


def _collect_engagement_context(engagement_path: Path) -> str | None:
    """Summarise available engagement data for the gate prompt.

    D-038: decisions and constraints are included with full bodies (capped)
    so the LLM can recognise when a persisted decision answers an
    information need and cite the ID(s) in ``have``.

    D-059: implementation now delegates to
    :func:`praxis.engagement.snapshot.render_snapshot_for_llm` with
    ``purpose="sufficiency"``. The single repo-read pass + per-purpose
    formatting policy live there. The empty-state contract (``None``
    when no entities are present) is preserved.
    """
    from praxis.engagement.snapshot import build_engagement_snapshot, render_snapshot_for_llm

    try:
        snapshot = build_engagement_snapshot(engagement_path)
    except Exception:  # noqa: BLE001 — gate must keep working even with a partial engagement
        return None

    rendered = render_snapshot_for_llm(snapshot, purpose="sufficiency")
    return rendered or None


# ---------------------------------------------------------------------------
# Cross-reference validation
# ---------------------------------------------------------------------------


def _validate_cross_refs(
    report: SufficiencyReport,
    engagement_path: Path | None,
) -> None:
    """Validate that referenced stakeholder IDs actually exist."""
    if not engagement_path:
        return

    if not report.elicitation_targets:
        # Also check candidate_sources with kind=stakeholder
        stakeholder_refs = set()
        for need in report.information_needs:
            for src in need.candidate_sources:
                if src.kind == "stakeholder":
                    stakeholder_refs.add(src.ref)
        if not stakeholder_refs:
            return
        all_refs = stakeholder_refs
    else:
        all_refs = set(report.elicitation_targets)
        for need in report.information_needs:
            for src in need.candidate_sources:
                if src.kind == "stakeholder":
                    all_refs.add(src.ref)

    from praxis.engagement import StakeholderRepo

    repo = StakeholderRepo(engagement_path)
    for ref in all_refs:
        if not repo.exists(ref):
            raise SufficiencyError(
                f"Stakeholder ID {ref!r} not found in engagement",
                stakeholder_id=ref,
            )


# ---------------------------------------------------------------------------
# Report persistence
# ---------------------------------------------------------------------------


def _persist_report(
    report: SufficiencyReport,
    engagement_path: Path,
) -> Path:
    """Save the report as an immutable JSON file."""
    reports_dir = engagement_path / ".praxis" / "state" / "sufficiency-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_id = uuid.uuid4().hex[:12]
    filename = f"{report_id}.json"
    path = reports_dir / filename

    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# JSON response parsing
# ---------------------------------------------------------------------------


def _parse_llm_response(raw: str) -> dict[str, object]:
    """Parse the LLM's JSON response, stripping markdown fences if present."""
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines if they're fences
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SufficiencyError(
            f"Failed to parse LLM response as JSON: {exc}",
            raw_response=raw[:500],
        ) from exc

    if not isinstance(data, dict):
        raise SufficiencyError(
            "LLM response is not a JSON object",
            raw_response=raw[:500],
        )

    return data


# ---------------------------------------------------------------------------
# Main gate runner
# ---------------------------------------------------------------------------


def run_sufficiency_gate(
    artifact_kind: str,
    artifact_target: str,
    *,
    transport: Transport,
    model: str = "default",
    engagement_path: Path | None = None,
    extra_context: str | None = None,
) -> SufficiencyReport:
    """Run the sufficiency gate for an artifact.

    Makes a single LLM call, parses and validates the structured response,
    persists the report, and emits an audit event.
    """
    # Build engagement context
    eng_context = _collect_engagement_context(engagement_path) if engagement_path else None

    # Build the prompt
    messages = _build_gate_prompt(
        artifact_kind,
        artifact_target,
        engagement_context=eng_context,
        extra_context=extra_context,
    )

    # Call the LLM
    request = ChatRequest(
        model=model,
        messages=messages,
        temperature=0.2,
        max_tokens=4096,
        stream=False,
    )

    response = transport.chat(request)

    if not response.content:
        raise SufficiencyError("LLM returned empty response")

    # Parse the JSON response
    data = _parse_llm_response(response.content)

    # Inject metadata
    data["generated_at"] = datetime.now(UTC).isoformat()
    data["by"] = "agent"
    data["schema_version"] = 1
    data["artifact_kind"] = artifact_kind
    data["artifact_target"] = artifact_target

    # Validate through Pydantic
    try:
        report = SufficiencyReport.model_validate(data)
    except Exception as exc:
        raise SufficiencyError(
            f"LLM response failed schema validation: {exc}",
            raw_data=str(data)[:500],
        ) from exc

    # Cross-reference validation
    _validate_cross_refs(report, engagement_path)

    # Persist
    if engagement_path:
        report_path = _persist_report(report, engagement_path)
        logger.info(
            "sufficiency.report_saved",
            path=str(report_path),
            verdict=report.verdict.value,
        )

    # Audit
    emit(
        "sufficiency.evaluated",
        component="sufficiency",
        subject_id=f"{artifact_kind}:{artifact_target}",
        engagement_path=engagement_path,
        verdict=report.verdict.value,
        recommended_action=report.recommended_action,
        needs_count=len(report.information_needs),
        blocker_count=sum(1 for n in report.information_needs if n.blocker),
    )

    return report
