"""Stakeholder repository — CRUD over the stakeholder map."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from praxis.audit import emit
from praxis.errors import EngagementError
from praxis.storage.files import read_yaml_typed, write_yaml_typed

from .._ids import stakeholder_id
from ..models import ContactChannel, Stakeholder, StakeholderMap


class StakeholderRepo:
    """Read/write the stakeholder map."""

    def __init__(self, engagement_path: Path) -> None:
        self._path = engagement_path / ".praxis" / "engagement" / "stakeholders.yaml"

    def load(self) -> StakeholderMap:
        """Load the stakeholder map."""
        return read_yaml_typed(self._path, StakeholderMap)

    def _save(self, smap: StakeholderMap) -> None:
        write_yaml_typed(self._path, smap)

    def get(self, sid: str) -> Stakeholder | None:
        """Get a stakeholder by ID."""
        smap = self.load()
        for s in smap.stakeholders:
            if s.id == sid:
                return s
        return None

    def list_all(self) -> list[Stakeholder]:
        """List all stakeholders."""
        return self.load().stakeholders

    def exists(self, sid: str) -> bool:
        """Check whether a stakeholder ID exists."""
        return self.get(sid) is not None

    def add(
        self,
        name: str,
        role: str,
        *,
        organization: str | None = None,
        expertise: list[str] | None = None,
        decision_authority: list[str] | None = None,
        consult_on: list[str] | None = None,
        contact_preference: ContactChannel = ContactChannel.EMAIL,
        contact_handle: str | None = None,
        notes: str | None = None,
        influence: str = "medium",
        interest: str = "medium",
    ) -> Stakeholder:
        """Add a new stakeholder."""
        smap = self.load()
        now = datetime.now(UTC)
        sid = stakeholder_id(name)

        s = Stakeholder(
            id=sid,
            name=name,
            role=role,
            organization=organization,
            expertise=expertise or [],
            decision_authority=decision_authority or [],
            consult_on=consult_on or [],
            contact_preference=contact_preference,
            contact_handle=contact_handle,
            notes=notes,
            influence=influence,  # type: ignore[arg-type]
            interest=interest,  # type: ignore[arg-type]
            created_at=now,
            updated_at=now,
        )
        smap.stakeholders.append(s)
        self._save(smap)
        emit("stakeholder.added", subject_id=sid, name=name)
        return s

    def update(self, sid: str, **kwargs: object) -> Stakeholder:
        """Update an existing stakeholder."""
        smap = self.load()
        for i, s in enumerate(smap.stakeholders):
            if s.id == sid:
                data = s.model_dump()
                data.update(kwargs)
                data["updated_at"] = datetime.now(UTC)
                smap.stakeholders[i] = Stakeholder.model_validate(data)
                self._save(smap)
                emit("stakeholder.updated", subject_id=sid)
                return smap.stakeholders[i]
        raise EngagementError(f"Stakeholder {sid!r} not found", id=sid)

    def remove(self, sid: str) -> None:
        """Remove a stakeholder by ID."""
        smap = self.load()
        original_len = len(smap.stakeholders)
        smap.stakeholders = [s for s in smap.stakeholders if s.id != sid]
        if len(smap.stakeholders) == original_len:
            raise EngagementError(f"Stakeholder {sid!r} not found", id=sid)
        self._save(smap)
        emit("stakeholder.removed", subject_id=sid)
