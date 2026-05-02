"""Tests for the Agent class, prompt builder, session helpers, and agent tools."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.config.models import ProfileConfig
from praxis.core.agent import Agent
from praxis.core.prompt import build_system_prompt
from praxis.core.session import (
    create_session,
    end_session,
    get_session,
    list_sessions,
    persist_message,
)
from praxis.storage.db import close_connection
from praxis.tools.models import ApprovalDecision
from praxis.tools.registry import ToolRegistry, default_registry
from praxis.transport.base import Transport
from praxis.transport.models import (
    ChatRequest,
    ChatResponse,
    ProbeResult,
    StreamChunk,
    ToolCall,
    Usage,
)

# ---------------------------------------------------------------------------
# Mock transport
# ---------------------------------------------------------------------------


class MockTransport(Transport):
    """Test transport that returns queued responses."""

    name = "mock"

    def __init__(self) -> None:
        self._queue: list[ChatResponse] = []

    def queue_response(
        self,
        text: str = "",
        tool_calls: list[ToolCall] | None = None,
        finish_reason: str | None = None,
    ) -> None:
        if finish_reason is None:
            finish_reason = "tool_use" if tool_calls else "stop"
        self._queue.append(
            ChatResponse(
                content=text,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=Usage(prompt_tokens=10, completion_tokens=5),
            )
        )

    def chat_stream(
        self,
        request: ChatRequest,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Iterator[StreamChunk]:
        if not self._queue:
            msg = "No queued responses"
            raise RuntimeError(msg)
        resp = self._queue.pop(0)
        yield StreamChunk(
            delta_text=resp.content if resp.content else None,
            finish_reason=resp.finish_reason,
            usage=resp.usage,
        )
        if resp.tool_calls:
            from praxis.transport.models import ToolCallDelta

            for i, tc in enumerate(resp.tool_calls):
                yield StreamChunk(
                    tool_call_delta=ToolCallDelta(
                        index=i,
                        id=tc.id,
                        name=tc.name,
                        arguments_delta=tc.arguments_json,
                    )
                )

    def supports_tools(self) -> bool:
        return True

    def supports_caching(self) -> bool:
        return False

    def probe(self) -> ProbeResult:
        return ProbeResult(ok=True, provider="mock", model="mock")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PROFILE = ProfileConfig(name="test")


@pytest.fixture()
def eng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create an initialized engagement for testing."""
    praxis_home = tmp_path / ".praxis"
    praxis_home.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PRAXIS_HOME", str(praxis_home))
    monkeypatch.delenv("PRAXIS_PROFILE", raising=False)

    eng_dir = tmp_path / "test-engagement"
    eng_dir.mkdir()
    init_engagement(eng_dir, "Test Engagement")
    yield eng_dir
    close_connection(eng_dir / ".praxis" / "state" / "praxis.db")


def _make_agent(
    eng: Path,
    transport: MockTransport | None = None,
    registry: ToolRegistry | None = None,
    approval_callback: object = None,
    max_iterations: int = 25,
) -> Agent:
    return Agent(
        profile=_PROFILE,
        engagement_path=eng,
        transport=transport or MockTransport(),
        tool_registry=registry or default_registry,
        approval_callback=approval_callback,  # type: ignore[arg-type]
        max_tool_iterations=max_iterations,
    )


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


class TestPromptBuilder:
    def test_deterministic(self) -> None:
        p1 = build_system_prompt(profile=_PROFILE)
        p2 = build_system_prompt(profile=_PROFILE)
        assert p1 == p2

    def test_contains_personality(self) -> None:
        prompt = build_system_prompt(profile=_PROFILE)
        assert "Praxis" in prompt

    def test_engagement_summary(self, eng: Path) -> None:
        from praxis.config.loader import load_engagement_config

        config = load_engagement_config(eng)
        prompt = build_system_prompt(
            profile=_PROFILE,
            engagement=config,
            engagement_path=eng,
        )
        assert "Test Engagement" in prompt

    def test_skill_index(self, eng: Path) -> None:
        from praxis.skills import SkillRegistry

        registry = SkillRegistry(engagement_path=eng)
        prompt = build_system_prompt(profile=_PROFILE, skill_registry=registry)
        # Even if no skills are active, the prompt should still be valid
        assert isinstance(prompt, str)

    def test_engagement_quick_refs(self, eng: Path) -> None:
        from praxis.engagement import GlossaryRepo

        # Add some data so quick refs show up
        repo = GlossaryRepo(eng)
        repo.add_term("invoice", "A request for payment")

        prompt = build_system_prompt(
            profile=_PROFILE,
            engagement_path=eng,
        )
        assert "1 glossary term" in prompt


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


class TestSessionHelpers:
    def test_create_and_get(self, eng: Path) -> None:
        db_path = eng / ".praxis" / "state" / "praxis.db"
        session = create_session(db_path, "test")
        assert session.id
        found = get_session(db_path, session.id)
        assert found is not None
        assert found.id == session.id

    def test_end_session(self, eng: Path) -> None:
        db_path = eng / ".praxis" / "state" / "praxis.db"
        session = create_session(db_path, "test")
        ended = end_session(db_path, session.id, summary="Done")
        assert ended.ended_at is not None
        assert ended.summary == "Done"

    def test_list_sessions(self, eng: Path) -> None:
        db_path = eng / ".praxis" / "state" / "praxis.db"
        create_session(db_path, "test")
        create_session(db_path, "test")
        sessions = list_sessions(db_path)
        assert len(sessions) == 2

    def test_persist_message(self, eng: Path) -> None:
        db_path = eng / ".praxis" / "state" / "praxis.db"
        session = create_session(db_path, "test")
        msg = persist_message(
            db_path,
            session_id=session.id,
            turn=1,
            role="user",
            content="Hello",
        )
        assert msg.id
        assert msg.content == "Hello"


# ---------------------------------------------------------------------------
# Agent: text-only response
# ---------------------------------------------------------------------------


class TestAgentTextOnly:
    def test_basic_turn(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_response(text="Hello from the agent!")

        agent = _make_agent(eng, transport)
        agent.start_session()
        resp = agent.turn("Hi there")

        assert "Hello from the agent" in resp.content
        assert resp.tool_call_count == 0
        assert resp.session_id

    def test_session_persisted(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_response(text="Ok")

        agent = _make_agent(eng, transport)
        sid = agent.start_session()
        agent.turn("Test")

        from praxis.storage.repos.sessions import SessionRepo

        db_path = eng / ".praxis" / "state" / "praxis.db"
        session = SessionRepo(db_path).get(sid)
        assert session is not None

    def test_end_session(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_response(text="Ok")

        agent = _make_agent(eng, transport)
        agent.start_session()
        agent.turn("Test")
        agent.end_session(summary="Test done")

        assert agent.session_id is None


# ---------------------------------------------------------------------------
# Agent: tool calls
# ---------------------------------------------------------------------------


class TestAgentToolCalls:
    def test_single_tool_call(self, eng: Path) -> None:
        transport = MockTransport()
        # First response: tool call
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="current_time",
                    arguments_json="{}",
                )
            ]
        )
        # Second response: text
        transport.queue_response(text="The time is now.")

        agent = _make_agent(eng, transport)
        agent.start_session()
        resp = agent.turn("What time is it?")

        assert "time" in resp.content.lower()
        assert resp.tool_call_count == 1

    def test_dangerous_tool_approved(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="glossary_add_term",
                    arguments_json='{"term":"invoice","definition":"A request for payment"}',
                )
            ]
        )
        transport.queue_response(text="Added invoice.")

        def approve(_spec: object, _args: object) -> ApprovalDecision:
            return ApprovalDecision.APPROVE

        agent = _make_agent(eng, transport, approval_callback=approve)
        agent.start_session()
        resp = agent.turn("Add invoice to glossary")

        assert resp.tool_call_count == 1

        # Verify engagement model was updated
        from praxis.engagement import GlossaryRepo

        glossary = GlossaryRepo(eng).load()
        assert any(t.term == "invoice" for t in glossary.terms)

    def test_max_iterations_cap(self, eng: Path) -> None:
        transport = MockTransport()
        # Queue many tool calls — more than max_iterations
        for _ in range(10):
            transport.queue_response(
                tool_calls=[ToolCall(id="c1", name="current_time", arguments_json="{}")]
            )

        agent = _make_agent(eng, transport, max_iterations=3)
        agent.start_session()
        resp = agent.turn("Loop forever")

        assert resp.truncated

    def test_cancellation(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_response(text="Ok")

        cancel = threading.Event()
        cancel.set()  # Already cancelled

        agent = _make_agent(eng, transport)
        agent.start_session()
        resp = agent.turn("Test", cancel_event=cancel)

        # Should get empty content due to cancellation
        assert resp.content == ""


# ---------------------------------------------------------------------------
# Agent: streaming
# ---------------------------------------------------------------------------


class TestAgentStreaming:
    def test_stream_turn(self, eng: Path) -> None:
        transport = MockTransport()
        transport.queue_response(text="Streamed response")

        agent = _make_agent(eng, transport)
        agent.start_session()
        events = list(agent.stream_turn("Hi"))

        types = [e.type for e in events]
        assert "text_delta" in types
        assert "done" in types


# ---------------------------------------------------------------------------
# Agent tools: current_time
# ---------------------------------------------------------------------------


class TestCurrentTimeTool:
    def test_returns_time(self, eng: Path) -> None:
        from praxis.tools.agent_tools import current_time
        from praxis.tools.context import ToolContext

        ctx = ToolContext(profile=_PROFILE)
        result = current_time(ctx)
        assert "T" in result.content  # ISO format


# ---------------------------------------------------------------------------
# Agent tools: read_file / write_file
# ---------------------------------------------------------------------------


class TestFileTools:
    def test_write_and_read(self, eng: Path) -> None:
        from praxis.tools.agent_tools import read_file, write_file
        from praxis.tools.context import ToolContext

        ctx = ToolContext(profile=_PROFILE, engagement_path=eng)

        write_result = write_file(ctx, "reports/test.txt", "Hello world")
        assert "Wrote" in write_result.content

        read_result = read_file(ctx, "reports/test.txt")
        assert read_result.content == "Hello world"

    def test_read_not_found(self, eng: Path) -> None:
        from praxis.tools.agent_tools import read_file
        from praxis.tools.context import ToolContext

        ctx = ToolContext(profile=_PROFILE, engagement_path=eng)
        result = read_file(ctx, "nonexistent.txt")
        assert "not found" in result.content.lower()

    def test_path_traversal_rejected(self, eng: Path) -> None:
        from praxis.errors import ToolError
        from praxis.tools.agent_tools import write_file
        from praxis.tools.context import ToolContext

        ctx = ToolContext(profile=_PROFILE, engagement_path=eng)
        with pytest.raises(ToolError, match="traversal"):
            write_file(ctx, "../../etc/passwd", "bad")

    def test_no_engagement_raises(self) -> None:
        from praxis.errors import ToolError
        from praxis.tools.agent_tools import read_file
        from praxis.tools.context import ToolContext

        ctx = ToolContext(profile=_PROFILE)
        with pytest.raises(ToolError, match="No engagement"):
            read_file(ctx, "test.txt")


# ---------------------------------------------------------------------------
# Agent tools: session_search
# ---------------------------------------------------------------------------


class TestSessionSearch:
    def test_no_engagement(self) -> None:
        from praxis.tools.agent_tools import session_search
        from praxis.tools.context import ToolContext

        ctx = ToolContext(profile=_PROFILE)
        result = session_search(ctx, "test")
        assert "No engagement" in result.content

    def test_search_finds_messages(self, eng: Path) -> None:
        from praxis.tools.agent_tools import session_search
        from praxis.tools.context import ToolContext

        # Persist a message to search for
        db_path = eng / ".praxis" / "state" / "praxis.db"
        session = create_session(db_path, "test")
        persist_message(
            db_path,
            session_id=session.id,
            turn=1,
            role="user",
            content="The invoice threshold is 10k",
        )

        ctx = ToolContext(profile=_PROFILE, engagement_path=eng)
        result = session_search(ctx, "invoice")
        assert "invoice" in result.content.lower()

    def test_search_no_results(self, eng: Path) -> None:
        from praxis.tools.agent_tools import session_search
        from praxis.tools.context import ToolContext

        ctx = ToolContext(profile=_PROFILE, engagement_path=eng)
        result = session_search(ctx, "xyznonexistent")
        assert "No messages" in result.content
