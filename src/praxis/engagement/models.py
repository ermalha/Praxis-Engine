"""Engagement model Pydantic models — the typed memory layer."""

from __future__ import annotations

from datetime import date, datetime  # noqa: TC003
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ContactChannel(StrEnum):
    """Communication channel preference."""

    EMAIL = "email"
    TEAMS = "teams"
    SLACK = "slack"
    PHONE = "phone"
    IN_PERSON = "in_person"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------


class GlossaryTerm(BaseModel):
    """A single domain term in the glossary."""

    model_config = ConfigDict(extra="forbid")

    term: str
    definition: str
    synonyms: list[str] = []
    notes: str | None = None
    sources: list[str] = []
    created_at: datetime
    updated_at: datetime


class Glossary(BaseModel):
    """The full engagement glossary."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    terms: list[GlossaryTerm] = []


# ---------------------------------------------------------------------------
# Stakeholders
# ---------------------------------------------------------------------------


class Stakeholder(BaseModel):
    """A project stakeholder."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    role: str
    organization: str | None = None
    expertise: list[str] = []
    decision_authority: list[str] = []
    consult_on: list[str] = []
    contact_preference: ContactChannel = ContactChannel.EMAIL
    contact_handle: str | None = None
    notes: str | None = None
    influence: Literal["low", "medium", "high"] = "medium"
    interest: Literal["low", "medium", "high"] = "medium"
    created_at: datetime
    updated_at: datetime


class StakeholderMap(BaseModel):
    """The full stakeholder map."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    stakeholders: list[Stakeholder] = []


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


class Decision(BaseModel):
    """An Architecture Decision Record (ADR)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    status: Literal["proposed", "accepted", "deprecated", "superseded"] = "proposed"
    context: str
    decision: str
    consequences: str
    alternatives: list[str] = []
    superseded_by: str | None = None
    decided_by: list[str] = []
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Open Questions
# ---------------------------------------------------------------------------


class OpenQuestion(BaseModel):
    """A tracked question awaiting an answer."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    why_it_matters: str
    candidate_answerers: list[str] = []
    status: Literal["open", "asked", "answered", "withdrawn"] = "open"
    answer: str | None = None
    blocks: list[str] = []
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    asked_at: datetime | None = None
    answered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OpenQuestions(BaseModel):
    """All tracked questions."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    questions: list[OpenQuestion] = []


# ---------------------------------------------------------------------------
# System Landscape
# ---------------------------------------------------------------------------


class System(BaseModel):
    """A system in the technology landscape."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: str
    owner: str | None = None
    status: Literal["live", "planned", "deprecated", "retired"] = "live"
    description: str | None = None
    tech_stack: list[str] = []
    integrations_with: list[str] = []
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class SystemLandscape(BaseModel):
    """The full system landscape."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    systems: list[System] = []


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------


class Risk(BaseModel):
    """A project risk."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str
    likelihood: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    mitigation: str | None = None
    owner: str | None = None
    status: Literal["open", "mitigated", "accepted", "transferred", "closed"] = "open"
    created_at: datetime
    updated_at: datetime


class RiskRegister(BaseModel):
    """The full risk register."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    risks: list[Risk] = []


# ---------------------------------------------------------------------------
# Assumptions & Constraints
# ---------------------------------------------------------------------------


class Assumption(BaseModel):
    """A project assumption."""

    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str
    rationale: str | None = None
    validated: bool = False
    validation_method: str | None = None
    invalidated_at: datetime | None = None
    created_at: datetime


class Constraint(BaseModel):
    """A project constraint."""

    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str
    source: str | None = None
    constraint_type: Literal["technical", "regulatory", "business", "schedule", "budget", "other"]
    created_at: datetime


class AssumptionsAndConstraints(BaseModel):
    """All assumptions and constraints."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    assumptions: list[Assumption] = []
    constraints: list[Constraint] = []


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


class Milestone(BaseModel):
    """A project milestone."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    target_date: date
    status: Literal["future", "in_progress", "achieved", "missed", "cancelled"] = "future"
    notes: str | None = None


class Timeline(BaseModel):
    """The project timeline."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    milestones: list[Milestone] = []
