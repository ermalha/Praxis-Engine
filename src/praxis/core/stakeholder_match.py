"""Stakeholder matching helpers for elicitation planning."""

from __future__ import annotations

from pathlib import Path

from praxis.engagement.models import Stakeholder


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase tokens for comparison."""
    return {w.lower().strip(".,;:!?") for w in text.split() if len(w) > 2}


def match_by_expertise(
    need_text: str,
    stakeholders: list[Stakeholder],
) -> list[Stakeholder]:
    """Find stakeholders with expertise matching the need text."""
    need_tokens = _tokenize(need_text)
    matches: list[tuple[int, Stakeholder]] = []

    for s in stakeholders:
        expertise_tokens: set[str] = set()
        for exp in s.expertise:
            expertise_tokens |= _tokenize(exp)
        # Also check consult_on
        for con in s.consult_on:
            expertise_tokens |= _tokenize(con)

        overlap = need_tokens & expertise_tokens
        if overlap:
            matches.append((len(overlap), s))

    matches.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in matches]


def match_by_authority(
    artifact_target: str,
    stakeholders: list[Stakeholder],
) -> list[Stakeholder]:
    """Find stakeholders with decision authority matching the artifact target."""
    target_tokens = _tokenize(artifact_target)
    matches: list[tuple[int, Stakeholder]] = []

    for s in stakeholders:
        auth_tokens: set[str] = set()
        for auth in s.decision_authority:
            auth_tokens |= _tokenize(auth)

        overlap = target_tokens & auth_tokens
        if overlap:
            matches.append((len(overlap), s))

    matches.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in matches]


def find_best_stakeholder(
    need_text: str,
    artifact_target: str,
    stakeholders: list[Stakeholder],
    *,
    preferred_ids: list[str] | None = None,
) -> Stakeholder | None:
    """Find the best stakeholder to answer a need.

    Priority:
    1. Preferred IDs (from sufficiency report candidate_sources)
    2. Expertise match
    3. Decision authority match
    4. None (caller should use UNKNOWN)
    """
    # 1. Try preferred IDs first
    if preferred_ids:
        by_id = {s.id: s for s in stakeholders}
        for pid in preferred_ids:
            if pid in by_id:
                return by_id[pid]

    # 2. Expertise match
    by_expertise = match_by_expertise(need_text, stakeholders)
    if by_expertise:
        return by_expertise[0]

    # 3. Authority match
    by_authority = match_by_authority(artifact_target, stakeholders)
    if by_authority:
        return by_authority[0]

    return None


def load_stakeholders(engagement_path: Path) -> list[Stakeholder]:
    """Load all stakeholders from the engagement model."""
    from praxis.engagement import StakeholderRepo

    return StakeholderRepo(engagement_path).list_all()
