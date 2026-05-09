"""Glossary repository — CRUD over engagement glossary terms."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from praxis.audit import emit
from praxis.errors import EngagementError
from praxis.storage.files import read_yaml_typed, write_yaml_typed

from ..models import Glossary, GlossaryTerm


class GlossaryRepo:
    """Read/write the engagement glossary."""

    def __init__(self, engagement_path: Path) -> None:
        self._path = engagement_path / ".praxis" / "engagement" / "glossary.yaml"

    def load(self) -> Glossary:
        """Load the glossary from disk."""
        return read_yaml_typed(self._path, Glossary)

    def _save(self, glossary: Glossary) -> None:
        write_yaml_typed(self._path, glossary)

    def get(self, term: str) -> GlossaryTerm | None:
        """Get a term by exact name (case-insensitive)."""
        glossary = self.load()
        lower = term.lower()
        for t in glossary.terms:
            if t.term.lower() == lower:
                return t
        return None

    def find(self, query: str) -> list[GlossaryTerm]:
        """Case-insensitive substring search on term, definition, synonyms, notes, sources."""
        glossary = self.load()
        lower = query.lower()
        results: list[GlossaryTerm] = []
        for t in glossary.terms:
            haystacks = [t.term, t.definition]
            if t.notes:
                haystacks.append(t.notes)
            haystacks.extend(t.synonyms)
            haystacks.extend(t.sources)
            if any(lower in h.lower() for h in haystacks):
                results.append(t)
        return results

    def add_term(
        self,
        term: str,
        definition: str,
        *,
        synonyms: list[str] | None = None,
        notes: str | None = None,
        sources: list[str] | None = None,
    ) -> GlossaryTerm:
        """Add a new term to the glossary."""
        glossary = self.load()
        if any(t.term.lower() == term.lower() for t in glossary.terms):
            raise EngagementError(f"Term {term!r} already exists", term=term)

        now = datetime.now(UTC)
        entry = GlossaryTerm(
            term=term,
            definition=definition,
            synonyms=synonyms or [],
            notes=notes,
            sources=sources or [],
            created_at=now,
            updated_at=now,
        )
        glossary.terms.append(entry)
        self._save(glossary)
        emit("glossary.term.added", subject_id=term, term=term)
        return entry

    def update_term(self, term: str, **kwargs: object) -> GlossaryTerm:
        """Update an existing term."""
        glossary = self.load()
        for i, t in enumerate(glossary.terms):
            if t.term.lower() == term.lower():
                data = t.model_dump()
                data.update(kwargs)
                data["updated_at"] = datetime.now(UTC)
                glossary.terms[i] = GlossaryTerm.model_validate(data)
                self._save(glossary)
                emit("glossary.term.updated", subject_id=term, term=term)
                return glossary.terms[i]
        raise EngagementError(f"Term {term!r} not found", term=term)

    def remove_term(self, term: str) -> None:
        """Remove a term from the glossary."""
        glossary = self.load()
        lower = term.lower()
        original_len = len(glossary.terms)
        glossary.terms = [t for t in glossary.terms if t.term.lower() != lower]
        if len(glossary.terms) == original_len:
            raise EngagementError(f"Term {term!r} not found", term=term)
        self._save(glossary)
        emit("glossary.term.removed", subject_id=term, term=term)
