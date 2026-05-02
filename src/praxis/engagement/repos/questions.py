"""Open questions repository — CRUD over tracked questions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from praxis.audit import emit
from praxis.errors import EngagementError
from praxis.storage.files import read_yaml_typed, write_yaml_typed

from .._ids import short_id
from ..models import OpenQuestion, OpenQuestions


class OpenQuestionsRepo:
    """Read/write tracked questions."""

    def __init__(self, engagement_path: Path) -> None:
        self._path = engagement_path / ".praxis" / "engagement" / "open-questions.yaml"
        self._engagement_path = engagement_path

    def _validate_stakeholder_refs(self, ids: list[str]) -> None:
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

    def load(self) -> OpenQuestions:
        """Load all questions."""
        return read_yaml_typed(self._path, OpenQuestions)

    def _save(self, data: OpenQuestions) -> None:
        write_yaml_typed(self._path, data)

    def list_all(self, *, status: str | None = None) -> list[OpenQuestion]:
        """List questions, optionally filtered by status."""
        questions = self.load().questions
        if status is not None:
            questions = [q for q in questions if q.status == status]
        return questions

    def get(self, qid: str) -> OpenQuestion | None:
        """Get a question by ID."""
        for q in self.load().questions:
            if q.id == qid:
                return q
        return None

    def open(
        self,
        question: str,
        why_it_matters: str,
        *,
        candidate_answerers: list[str] | None = None,
        blocks: list[str] | None = None,
        priority: str = "medium",
    ) -> OpenQuestion:
        """Open a new question."""
        candidate_answerers = candidate_answerers or []
        self._validate_stakeholder_refs(candidate_answerers)

        data = self.load()
        now = datetime.now(UTC)
        qid = short_id()

        q = OpenQuestion(
            id=qid,
            question=question,
            why_it_matters=why_it_matters,
            candidate_answerers=candidate_answerers,
            status="open",
            blocks=blocks or [],
            priority=priority,  # type: ignore[arg-type]
            created_at=now,
            updated_at=now,
        )
        data.questions.append(q)
        self._save(data)
        emit("question.opened", subject_id=qid, question=question)
        return q

    def answer(self, qid: str, answer: str) -> OpenQuestion:
        """Record an answer for a question."""
        data = self.load()
        now = datetime.now(UTC)
        for i, q in enumerate(data.questions):
            if q.id == qid:
                updated = q.model_copy(
                    update={
                        "status": "answered",
                        "answer": answer,
                        "answered_at": now,
                        "updated_at": now,
                    }
                )
                data.questions[i] = updated
                self._save(data)
                emit("question.answered", subject_id=qid)
                return updated
        raise EngagementError(f"Question {qid!r} not found", id=qid)

    def withdraw(self, qid: str) -> OpenQuestion:
        """Withdraw a question."""
        data = self.load()
        now = datetime.now(UTC)
        for i, q in enumerate(data.questions):
            if q.id == qid:
                updated = q.model_copy(update={"status": "withdrawn", "updated_at": now})
                data.questions[i] = updated
                self._save(data)
                emit("question.withdrawn", subject_id=qid)
                return updated
        raise EngagementError(f"Question {qid!r} not found", id=qid)
