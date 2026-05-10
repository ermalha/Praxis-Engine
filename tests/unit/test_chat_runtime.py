"""Tests for shared chat runtime used by CLI and TUI."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from praxis.config.engagement import init_engagement
from praxis.config.models import ProfileConfig
from praxis.core.chat_runtime import ChatRuntime, SlashResult
from praxis.core.models import StreamEvent
from praxis.storage.db import close_connection
from praxis.storage.models import Session
from praxis.storage.repos.sessions import SessionRepo


class FakeAgent:
    """Minimal Agent stand-in for runtime tests."""

    def __init__(self, **_: Any) -> None:
        self.started = 0
        self.ended = 0
        self.messages: list[str] = []
        self.session_id = "fake-session-1"

    def start_session(self, parent_id: str | None = None) -> str:
        self.started += 1
        self.session_id = f"fake-session-{self.started}"
        return self.session_id

    def end_session(self, summary: str | None = None) -> None:
        self.ended += 1

    def stream_turn(
        self,
        user_input: str,
        *,
        cancel_event: object | None = None,
    ) -> list[StreamEvent]:
        self.messages.append(user_input)
        return [
            StreamEvent(type="text_delta", text=f"Echo: {user_input}"),
            StreamEvent(type="done"),
        ]


@pytest.fixture()
def eng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    praxis_home = tmp_path / ".praxis-home"
    praxis_home.mkdir()
    monkeypatch.setenv("PRAXIS_HOME", str(praxis_home))
    monkeypatch.setenv("HOME", str(tmp_path))

    eng_dir = tmp_path / "engagement"
    eng_dir.mkdir()
    init_engagement(eng_dir, "Runtime Test")
    yield eng_dir
    close_connection(eng_dir / ".praxis" / "state" / "praxis.db")


def make_runtime(eng: Path, fake_agent: FakeAgent) -> ChatRuntime:
    return ChatRuntime(
        profile=ProfileConfig(name="default"),
        engagement_path=eng,
        engagement=None,
        model="fake-model",
        transport=None,
        agent=fake_agent,
    )


def test_runtime_start_and_close_session(eng: Path) -> None:
    fake = FakeAgent()
    runtime = make_runtime(eng, fake)

    sid = runtime.start()
    runtime.close()

    assert sid == "fake-session-1"
    assert fake.started == 1
    assert fake.ended == 1


def test_runtime_stream_turn_starts_session_and_delegates_to_agent(eng: Path) -> None:
    fake = FakeAgent()
    runtime = make_runtime(eng, fake)

    events = list(runtime.stream_turn("hello"))

    assert fake.started == 1
    assert fake.messages == ["hello"]
    assert [event.text for event in events if event.text] == ["Echo: hello"]


def test_runtime_slash_help_returns_text(eng: Path) -> None:
    runtime = make_runtime(eng, FakeAgent())

    result = runtime.handle_slash("/help")

    assert isinstance(result, SlashResult)
    assert result.continue_session is True
    assert "/exit" in result.text
    assert "/tools" in result.text


def test_runtime_slash_exit_requests_stop(eng: Path) -> None:
    runtime = make_runtime(eng, FakeAgent())

    result = runtime.handle_slash("/exit")

    assert result.continue_session is False


def test_runtime_slash_new_restarts_session(eng: Path) -> None:
    fake = FakeAgent()
    runtime = make_runtime(eng, fake)
    runtime.start()

    result = runtime.handle_slash("/new")

    assert result.continue_session is True
    assert fake.ended == 1
    assert fake.started == 2
    assert "New session" in result.text


def test_runtime_slash_sessions_lists_session_store(eng: Path) -> None:
    db_path = eng / ".praxis" / "state" / "praxis.db"
    SessionRepo(db_path).create(
        Session(id="stored-session", profile="default", started_at=datetime.now(UTC))
    )
    runtime = make_runtime(eng, FakeAgent())

    result = runtime.handle_slash("/sessions")

    assert result.continue_session is True
    assert "active" in result.text


def test_runtime_unknown_slash_reports_error(eng: Path) -> None:
    runtime = make_runtime(eng, FakeAgent())

    result = runtime.handle_slash("/wat")

    assert result.continue_session is True
    assert "Unknown command" in result.text
