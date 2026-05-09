"""Decision repository — ADR-style decision records stored as Markdown files."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from praxis.audit import emit
from praxis.errors import EngagementError
from praxis.storage.files import read_markdown_with_frontmatter, write_markdown_with_frontmatter

from .._ids import decision_id
from ..models import Decision


class DecisionRepo:
    """Read/write Architecture Decision Records."""

    def __init__(self, engagement_path: Path) -> None:
        self._dir = engagement_path / ".praxis" / "engagement" / "decisions"
        self._engagement_path = engagement_path

    def _validate_stakeholder_refs(self, ids: list[str]) -> None:
        """Validate that stakeholder IDs exist."""
        if not ids:
            return
        from .stakeholders import StakeholderRepo

        repo = StakeholderRepo(self._engagement_path)
        for sid in ids:
            if not repo.exists(sid):
                raise EngagementError(
                    f"Stakeholder {sid!r} not found",
                    id=sid,
                )

    def list_all(self) -> list[Decision]:
        """List all decisions."""
        decisions: list[Decision] = []
        if not self._dir.is_dir():
            return decisions
        for path in sorted(self._dir.glob("*.md")):
            fm, _body = read_markdown_with_frontmatter(path, Decision)
            decisions.append(fm)
        return decisions

    def get(self, did: str) -> tuple[Decision, str] | None:
        """Get a decision by ID, returning (frontmatter, body)."""
        path = self._dir / f"{did}.md"
        if not path.exists():
            return None
        fm, body = read_markdown_with_frontmatter(path, Decision)
        return fm, body

    def create(
        self,
        title: str,
        context: str,
        decision: str,
        consequences: str,
        *,
        alternatives: list[str] | None = None,
        decided_by: list[str] | None = None,
        status: str = "proposed",
    ) -> Decision:
        """Create a new ADR."""
        decided_by = decided_by or []
        self._validate_stakeholder_refs(decided_by)

        did = decision_id(title)
        now = datetime.now(UTC)

        d = Decision(
            id=did,
            title=title,
            status=status,  # type: ignore[arg-type]
            context=context,
            decision=decision,
            consequences=consequences,
            alternatives=alternatives or [],
            decided_by=decided_by,
            created_at=now,
            updated_at=now,
        )

        body = (
            f"\n# {title}\n\n## Context\n\n{context}\n\n"
            f"## Decision\n\n{decision}\n\n## Consequences\n\n{consequences}\n"
        )
        if alternatives:
            body += "\n## Alternatives Considered\n\n"
            for alt in alternatives:
                body += f"- {alt}\n"

        path = self._dir / f"{did}.md"
        write_markdown_with_frontmatter(path, d, body)
        emit("decision.created", subject_id=did, title=title)
        return d

    def update(self, did: str, **kwargs: object) -> Decision:
        """Update an existing decision."""
        result = self.get(did)
        if result is None:
            raise EngagementError(f"Decision {did!r} not found", id=did)

        fm, body = result
        data = fm.model_dump()
        data.update(kwargs)
        data["updated_at"] = datetime.now(UTC)
        new_fm = Decision.model_validate(data)

        path = self._dir / f"{did}.md"
        write_markdown_with_frontmatter(path, new_fm, body)
        emit("decision.updated", subject_id=did)
        return new_fm

    def supersede(self, did: str, superseded_by: str) -> Decision:
        """Mark a decision as superseded."""
        if did == superseded_by:
            raise EngagementError(
                f"Decision {did!r} cannot supersede itself",
                id=did,
            )
        return self.update(did, status="superseded", superseded_by=superseded_by)
