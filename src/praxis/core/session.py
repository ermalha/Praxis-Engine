"""Session lifecycle helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from praxis.storage.models import Message as StoredMessage
from praxis.storage.models import Session
from praxis.storage.repos.messages import MessageRepo
from praxis.storage.repos.sessions import SessionRepo
from praxis.transport.models import Message as TransportMessage


def create_session(
    db_path: Path,
    profile: str,
    *,
    parent_id: str | None = None,
) -> Session:
    """Create and persist a new session."""
    repo = SessionRepo(db_path)
    session = Session(
        id=str(uuid.uuid4()),
        parent_id=parent_id,
        profile=profile,
        started_at=datetime.now(UTC),
    )
    return repo.create(session)


def end_session(
    db_path: Path,
    session_id: str,
    *,
    summary: str | None = None,
) -> Session:
    """End a session, setting ended_at and optional summary."""
    repo = SessionRepo(db_path)
    session = repo.get(session_id)
    if session is None:
        msg = f"Session {session_id!r} not found"
        raise ValueError(msg)
    updated = session.model_copy(
        update={
            "ended_at": datetime.now(UTC),
            "summary": summary,
        }
    )
    return repo.update(updated)


def list_sessions(db_path: Path, *, limit: int = 20) -> list[Session]:
    """List recent sessions."""
    return SessionRepo(db_path).list(limit=limit)


def get_session(db_path: Path, session_id: str) -> Session | None:
    """Get a session by ID."""
    return SessionRepo(db_path).get(session_id)


def load_session_messages(
    db_path: Path,
    session_id: str,
) -> list[TransportMessage]:
    """Load messages for a session and convert to transport format."""
    repo = MessageRepo(db_path)
    stored = repo.list_by_session(session_id)
    messages: list[TransportMessage] = []
    for m in stored:
        msg = TransportMessage(
            role=m.role.value,
            content=m.content,
        )
        if m.tool_calls_json:
            import json

            from praxis.transport.models import ToolCall

            calls = json.loads(m.tool_calls_json)
            msg = msg.model_copy(update={"tool_calls": [ToolCall.model_validate(c) for c in calls]})
        messages.append(msg)
    return messages


def persist_message(
    db_path: Path,
    *,
    session_id: str,
    turn: int,
    role: str,
    content: str,
    tool_calls_json: str | None = None,
) -> StoredMessage:
    """Persist a single message to the database."""
    repo = MessageRepo(db_path)
    msg = StoredMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        turn=turn,
        role=role,  # type: ignore[arg-type]
        content=content,
        tool_calls_json=tool_calls_json,
        created_at=datetime.now(UTC),
    )
    return repo.create(msg)
