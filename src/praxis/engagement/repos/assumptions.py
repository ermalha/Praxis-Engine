"""Assumptions and constraints repository."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from praxis.audit import emit
from praxis.errors import EngagementError
from praxis.storage.files import read_yaml_typed, write_yaml_typed

from .._ids import short_id
from ..models import Assumption, AssumptionsAndConstraints, Constraint


class AssumptionsConstraintsRepo:
    """Read/write assumptions and constraints."""

    def __init__(self, engagement_path: Path) -> None:
        self._path = engagement_path / ".praxis" / "engagement" / "assumptions-and-constraints.yaml"

    def load(self) -> AssumptionsAndConstraints:
        return read_yaml_typed(self._path, AssumptionsAndConstraints)

    def _save(self, data: AssumptionsAndConstraints) -> None:
        write_yaml_typed(self._path, data)

    def list_assumptions(self) -> list[Assumption]:
        return self.load().assumptions

    def list_constraints(self) -> list[Constraint]:
        return self.load().constraints

    def add_assumption(
        self,
        statement: str,
        *,
        rationale: str | None = None,
        validation_method: str | None = None,
    ) -> Assumption:
        """Add an assumption."""
        data = self.load()
        aid = short_id()
        now = datetime.now(UTC)

        a = Assumption(
            id=aid,
            statement=statement,
            rationale=rationale,
            validation_method=validation_method,
            created_at=now,
        )
        data.assumptions.append(a)
        self._save(data)
        emit("assumption.added", subject_id=aid, statement=statement)
        return a

    def add_constraint(
        self,
        statement: str,
        constraint_type: str,
        *,
        source: str | None = None,
    ) -> Constraint:
        """Add a constraint."""
        data = self.load()
        cid = short_id()
        now = datetime.now(UTC)

        c = Constraint(
            id=cid,
            statement=statement,
            constraint_type=constraint_type,  # type: ignore[arg-type]
            source=source,
            created_at=now,
        )
        data.constraints.append(c)
        self._save(data)
        emit("constraint.added", subject_id=cid, statement=statement)
        return c

    def validate_assumption(self, aid: str) -> Assumption:
        """Mark an assumption as validated."""
        data = self.load()
        for i, a in enumerate(data.assumptions):
            if a.id == aid:
                updated = a.model_copy(update={"validated": True})
                data.assumptions[i] = updated
                self._save(data)
                emit("assumption.validated", subject_id=aid)
                return updated
        raise EngagementError(f"Assumption {aid!r} not found", id=aid)

    def invalidate_assumption(self, aid: str) -> Assumption:
        """Mark an assumption as invalidated."""
        data = self.load()
        now = datetime.now(UTC)
        for i, a in enumerate(data.assumptions):
            if a.id == aid:
                updated = a.model_copy(update={"invalidated_at": now})
                data.assumptions[i] = updated
                self._save(data)
                emit("assumption.invalidated", subject_id=aid)
                return updated
        raise EngagementError(f"Assumption {aid!r} not found", id=aid)
