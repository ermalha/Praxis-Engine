"""System landscape repository."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from praxis.audit import emit
from praxis.errors import EngagementError
from praxis.storage.files import read_yaml_typed, write_yaml_typed

from .._ids import short_id
from ..models import System, SystemLandscape


class SystemLandscapeRepo:
    """Read/write the system landscape."""

    def __init__(self, engagement_path: Path) -> None:
        self._path = engagement_path / ".praxis" / "engagement" / "system-landscape.yaml"

    def load(self) -> SystemLandscape:
        return read_yaml_typed(self._path, SystemLandscape)

    def _save(self, data: SystemLandscape) -> None:
        write_yaml_typed(self._path, data)

    def list_all(self) -> list[System]:
        return self.load().systems

    def get(self, sid: str) -> System | None:
        for s in self.load().systems:
            if s.id == sid:
                return s
        return None

    def add(
        self,
        name: str,
        kind: str,
        *,
        owner: str | None = None,
        description: str | None = None,
        tech_stack: list[str] | None = None,
        integrations_with: list[str] | None = None,
        notes: str | None = None,
    ) -> System:
        """Add a system to the landscape."""
        data = self.load()
        now = datetime.now(UTC)
        sid = short_id()

        s = System(
            id=sid,
            name=name,
            kind=kind,
            owner=owner,
            description=description,
            tech_stack=tech_stack or [],
            integrations_with=integrations_with or [],
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        data.systems.append(s)
        self._save(data)
        emit("system.added", subject_id=sid, name=name)
        return s

    def update(self, sid: str, **kwargs: object) -> System:
        """Update an existing system."""
        data = self.load()
        for i, s in enumerate(data.systems):
            if s.id == sid:
                d = s.model_dump()
                d.update(kwargs)
                d["updated_at"] = datetime.now(UTC)
                data.systems[i] = System.model_validate(d)
                self._save(data)
                emit("system.updated", subject_id=sid)
                return data.systems[i]
        raise EngagementError(f"System {sid!r} not found", id=sid)
