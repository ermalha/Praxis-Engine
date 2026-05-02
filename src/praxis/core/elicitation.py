"""Elicitation Planner — drafts targeted messages to fill information gaps."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

import structlog
from pydantic import BaseModel, ConfigDict

from praxis.audit import emit
from praxis.engagement.models import ContactChannel
from praxis.errors import SufficiencyError
from praxis.transport.base import Transport
from praxis.transport.models import ChatRequest, Message

from .stakeholder_match import load_stakeholders
from .sufficiency import SufficiencyReport

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums & Models
# ---------------------------------------------------------------------------


class ElicitationMode(StrEnum):
    DIRECT_QUESTION = "direct_question"
    EMAIL = "email"
    MEETING_REQUEST = "meeting_request"
    WORKSHOP = "workshop"
    DOCUMENT_REQUEST = "document_request"
    SHADOWING = "shadowing"


class ElicitationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    target_stakeholder_id: str
    target_stakeholder_name: str
    channel: ContactChannel
    mode: ElicitationMode
    priority: Literal["critical", "high", "medium", "low"]
    rationale: str
    related_info_needs: list[str]
    blocks: list[str] = []
    drafted_subject: str | None = None
    drafted_body: str
    expected_response_format: str
    followup_after_days: int = 3
    deadline: datetime | None = None


# ---------------------------------------------------------------------------
# Sub-prompt for the LLM
# ---------------------------------------------------------------------------

_PLANNER_SYSTEM_PROMPT = """\
You are an elicitation planner for a business analyst agent. Given a \
sufficiency report and stakeholder information, produce targeted \
elicitation drafts.

You MUST respond with a JSON array of draft objects:
[
  {
    "target_stakeholder_id": "<id or UNKNOWN>",
    "target_stakeholder_name": "<name or 'Unknown — please identify'>",
    "channel": "email"|"teams"|"slack"|"phone"|"in_person"|"other",
    "mode": "direct_question"|"email"|"meeting_request"|"workshop"|\
"document_request"|"shadowing",
    "priority": "critical"|"high"|"medium"|"low",
    "rationale": "<why this person, why this mode>",
    "related_info_needs": ["<need text>", ...],
    "blocks": [],
    "drafted_subject": "<subject for emails, or null>",
    "drafted_body": "<the actual message / question>",
    "expected_response_format": "free text"|"yes/no"|"list of items"|"document",
    "followup_after_days": 3
  }
]

Rules:
- Group needs by stakeholder where possible (fewer, richer messages).
- For 1-2 simple needs: use direct_question mode.
- For 3+ needs or complex topics: use meeting_request.
- For 5+ needs across topics: use workshop.
- For document/artifact needs: use document_request.
- Choose channel from the stakeholder's contact_preference.
- Prioritise blockers as "critical" or "high".
- If no stakeholder is identified, use id="UNKNOWN" and ask the operator.

Respond ONLY with the JSON array. No markdown fences, no extra text."""


def _build_planner_prompt(
    report: SufficiencyReport,
    stakeholder_context: str,
) -> list[Message]:
    """Build the prompt for the elicitation planner LLM call."""
    needs_text = "\n".join(
        f"- {n.need} [status={n.status}, blocker={n.blocker}]"
        + (f" (have: {n.have})" if n.have else "")
        + (f" (missing: {n.missing})" if n.missing else "")
        for n in report.information_needs
        if n.status in ("unknown", "partial")
    )

    user_parts = [
        f"Artifact: {report.artifact_kind} — {report.artifact_target}",
        f"Verdict: {report.verdict}",
        f"\nInformation gaps:\n{needs_text}",
    ]

    if stakeholder_context:
        user_parts.append(f"\nKnown stakeholders:\n{stakeholder_context}")

    return [
        Message(role="system", content=_PLANNER_SYSTEM_PROMPT),
        Message(role="user", content="\n\n".join(user_parts)),
    ]


# ---------------------------------------------------------------------------
# Draft persistence
# ---------------------------------------------------------------------------


def _persist_drafts(
    drafts: list[ElicitationDraft],
    engagement_path: Path,
) -> Path:
    """Save drafts to disk."""
    drafts_dir = engagement_path / ".praxis" / "state" / "elicitation-drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    batch_id = uuid.uuid4().hex[:12]
    path = drafts_dir / f"{batch_id}.json"

    data = [d.model_dump(mode="json") for d in drafts]
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# OpenQuestion creation
# ---------------------------------------------------------------------------


def _create_open_questions(
    drafts: list[ElicitationDraft],
    engagement_path: Path,
) -> None:
    """Auto-create OpenQuestion entries for each draft."""
    from praxis.engagement import OpenQuestionsRepo

    repo = OpenQuestionsRepo(engagement_path)

    for draft in drafts:
        for need_text in draft.related_info_needs:
            # Check if question already exists
            existing = repo.load().questions
            already_exists = any(need_text.lower() in q.question.lower() for q in existing)
            if already_exists:
                continue

            answerers = (
                [draft.target_stakeholder_id] if draft.target_stakeholder_id != "UNKNOWN" else []
            )

            repo.open(
                question=need_text,
                why_it_matters=draft.rationale,
                candidate_answerers=answerers,
                priority=draft.priority,
            )


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def _parse_planner_response(raw: str) -> list[dict[str, object]]:
    """Parse the LLM's JSON array response."""
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SufficiencyError(
            f"Failed to parse planner response: {exc}",
            raw_response=raw[:500],
        ) from exc

    if not isinstance(data, list):
        raise SufficiencyError(
            "Planner response is not a JSON array",
            raw_response=raw[:500],
        )

    return data


# ---------------------------------------------------------------------------
# Main planner
# ---------------------------------------------------------------------------


def plan_elicitations(
    sufficiency_report: SufficiencyReport,
    *,
    transport: Transport,
    model: str = "default",
    engagement_path: Path | None = None,
    max_drafts: int = 5,
) -> list[ElicitationDraft]:
    """Plan elicitations from a sufficiency report.

    Produces draft messages for each gap, auto-creates OpenQuestion entries,
    and persists drafts to disk.
    """
    # Collect gaps
    gaps = [n for n in sufficiency_report.information_needs if n.status in ("unknown", "partial")]
    if not gaps:
        return []

    # Build stakeholder context
    stakeholder_context = ""
    if engagement_path:
        stakeholders = load_stakeholders(engagement_path)
        if stakeholders:
            lines = []
            for s in stakeholders:
                parts = [f"{s.id}: {s.name} ({s.role})"]
                if s.expertise:
                    parts.append(f"expertise={s.expertise}")
                if s.contact_preference:
                    parts.append(f"prefers={s.contact_preference}")
                if s.contact_handle:
                    parts.append(f"handle={s.contact_handle}")
                lines.append("  ".join(parts))
            stakeholder_context = "\n".join(lines)

    # Call LLM
    messages = _build_planner_prompt(sufficiency_report, stakeholder_context)
    request = ChatRequest(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=4096,
        stream=False,
    )

    response = transport.chat(request)
    if not response.content:
        raise SufficiencyError("Planner LLM returned empty response")

    raw_drafts = _parse_planner_response(response.content)

    # Validate and construct drafts
    drafts: list[ElicitationDraft] = []
    for raw in raw_drafts[:max_drafts]:
        raw["schema_version"] = 1
        try:
            draft = ElicitationDraft.model_validate(raw)
            drafts.append(draft)
        except Exception:  # noqa: BLE001
            logger.warning(
                "elicitation.invalid_draft",
                raw=str(raw)[:200],
            )
            continue

    # Persist drafts
    if engagement_path and drafts:
        draft_path = _persist_drafts(drafts, engagement_path)
        logger.info("elicitation.drafts_saved", path=str(draft_path))

        # Auto-create open questions
        _create_open_questions(drafts, engagement_path)

    # Audit
    emit(
        "elicitation.planned",
        component="elicitation",
        subject_id=f"{sufficiency_report.artifact_kind}:{sufficiency_report.artifact_target}",
        engagement_path=engagement_path,
        draft_count=len(drafts),
        gap_count=len(gaps),
    )

    return drafts
