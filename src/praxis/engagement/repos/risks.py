"""Risk register repository."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from praxis.audit import emit
from praxis.errors import EngagementError
from praxis.storage.files import read_yaml_typed, write_yaml_typed

from .._ids import short_id
from ..models import Risk, RiskRegister


class RiskRepo:
    """Read/write the risk register."""

    def __init__(self, engagement_path: Path) -> None:
        self._path = engagement_path / ".praxis" / "engagement" / "risks.yaml"

    def load(self) -> RiskRegister:
        return read_yaml_typed(self._path, RiskRegister)

    def _save(self, data: RiskRegister) -> None:
        write_yaml_typed(self._path, data)

    def list_all(self) -> list[Risk]:
        return self.load().risks

    def get(self, rid: str) -> Risk | None:
        for r in self.load().risks:
            if r.id == rid:
                return r
        return None

    def add(
        self,
        title: str,
        description: str,
        likelihood: str,
        impact: str,
        *,
        mitigation: str | None = None,
        owner: str | None = None,
    ) -> Risk:
        """Add a risk to the register."""
        data = self.load()
        now = datetime.now(UTC)
        rid = short_id()

        r = Risk(
            id=rid,
            title=title,
            description=description,
            likelihood=likelihood,  # type: ignore[arg-type]
            impact=impact,  # type: ignore[arg-type]
            mitigation=mitigation,
            owner=owner,
            created_at=now,
            updated_at=now,
        )
        data.risks.append(r)
        self._save(data)
        emit("risk.added", subject_id=rid, title=title)
        return r

    def update(self, rid: str, **kwargs: object) -> Risk:
        """Update an existing risk."""
        data = self.load()
        for i, r in enumerate(data.risks):
            if r.id == rid:
                d = r.model_dump()
                d.update(kwargs)
                d["updated_at"] = datetime.now(UTC)
                data.risks[i] = Risk.model_validate(d)
                self._save(data)
                emit("risk.updated", subject_id=rid)
                return data.risks[i]
        raise EngagementError(f"Risk {rid!r} not found", id=rid)

    def close(self, rid: str) -> Risk:
        """Close a risk."""
        return self.update(rid, status="closed")
