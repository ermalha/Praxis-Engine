"""Timeline repository."""

from __future__ import annotations

from datetime import date  # noqa: TC003
from pathlib import Path

from praxis.audit import emit
from praxis.errors import EngagementError
from praxis.storage.files import read_yaml_typed, write_yaml_typed

from .._ids import short_id
from ..models import Milestone, Timeline


class TimelineRepo:
    """Read/write project milestones."""

    def __init__(self, engagement_path: Path) -> None:
        self._path = engagement_path / ".praxis" / "engagement" / "timeline.yaml"

    def load(self) -> Timeline:
        return read_yaml_typed(self._path, Timeline)

    def _save(self, data: Timeline) -> None:
        write_yaml_typed(self._path, data)

    def list_all(self) -> list[Milestone]:
        return self.load().milestones

    def get(self, mid: str) -> Milestone | None:
        for m in self.load().milestones:
            if m.id == mid:
                return m
        return None

    def add(
        self,
        title: str,
        target_date: date,
        *,
        notes: str | None = None,
    ) -> Milestone:
        """Add a milestone."""
        data = self.load()
        mid = short_id()

        m = Milestone(
            id=mid,
            title=title,
            target_date=target_date,
            notes=notes,
        )
        data.milestones.append(m)
        self._save(data)
        emit("milestone.added", subject_id=mid, title=title)
        return m

    def update(self, mid: str, **kwargs: object) -> Milestone:
        """Update an existing milestone."""
        data = self.load()
        for i, m in enumerate(data.milestones):
            if m.id == mid:
                d = m.model_dump()
                d.update(kwargs)
                data.milestones[i] = Milestone.model_validate(d)
                self._save(data)
                emit("milestone.updated", subject_id=mid)
                return data.milestones[i]
        raise EngagementError(f"Milestone {mid!r} not found", id=mid)
