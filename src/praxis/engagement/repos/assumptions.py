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

    # ---------------------------------------------------------------
    # D-052 — assumption get / update / remove
    # ---------------------------------------------------------------

    def get_assumption(self, aid: str) -> Assumption:
        """Return the assumption with id *aid*, or raise EngagementError."""
        for a in self.load().assumptions:
            if a.id == aid:
                return a
        raise EngagementError(f"Assumption {aid!r} not found", id=aid)

    def update_assumption(
        self,
        aid: str,
        *,
        statement: str | None = None,
        rationale: str | None = None,
        validation_method: str | None = None,
    ) -> Assumption:
        """Update mutable fields on an assumption. Only non-None args are written."""
        data = self.load()
        for i, a in enumerate(data.assumptions):
            if a.id == aid:
                updates: dict[str, object] = {}
                if statement is not None:
                    updates["statement"] = statement
                if rationale is not None:
                    updates["rationale"] = rationale
                if validation_method is not None:
                    updates["validation_method"] = validation_method
                if not updates:
                    return a
                updated = a.model_copy(update=updates)
                data.assumptions[i] = updated
                self._save(data)
                emit("assumption.updated", subject_id=aid, fields=sorted(updates))
                return updated
        raise EngagementError(f"Assumption {aid!r} not found", id=aid)

    def remove_assumption(self, aid: str) -> None:
        """Remove the assumption with id *aid*, or raise EngagementError."""
        data = self.load()
        for i, a in enumerate(data.assumptions):
            if a.id == aid:
                del data.assumptions[i]
                self._save(data)
                emit("assumption.removed", subject_id=aid)
                return
        raise EngagementError(f"Assumption {aid!r} not found", id=aid)

    # ---------------------------------------------------------------
    # D-052 — constraint get / update / remove
    # ---------------------------------------------------------------

    def get_constraint(self, cid: str) -> Constraint:
        """Return the constraint with id *cid*, or raise EngagementError."""
        for c in self.load().constraints:
            if c.id == cid:
                return c
        raise EngagementError(f"Constraint {cid!r} not found", id=cid)

    def update_constraint(
        self,
        cid: str,
        *,
        statement: str | None = None,
        constraint_type: str | None = None,
        source: str | None = None,
    ) -> Constraint:
        """Update mutable fields on a constraint. Only non-None args are written."""
        data = self.load()
        for i, c in enumerate(data.constraints):
            if c.id == cid:
                updates: dict[str, object] = {}
                if statement is not None:
                    updates["statement"] = statement
                if constraint_type is not None:
                    updates["constraint_type"] = constraint_type
                if source is not None:
                    updates["source"] = source
                if not updates:
                    return c
                updated = c.model_copy(update=updates)
                data.constraints[i] = updated
                self._save(data)
                emit("constraint.updated", subject_id=cid, fields=sorted(updates))
                return updated
        raise EngagementError(f"Constraint {cid!r} not found", id=cid)

    def remove_constraint(self, cid: str) -> None:
        """Remove the constraint with id *cid*, or raise EngagementError."""
        data = self.load()
        for i, c in enumerate(data.constraints):
            if c.id == cid:
                del data.constraints[i]
                self._save(data)
                emit("constraint.removed", subject_id=cid)
                return
        raise EngagementError(f"Constraint {cid!r} not found", id=cid)

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
