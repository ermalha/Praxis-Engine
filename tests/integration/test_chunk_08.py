"""Integration test for Chunk 08 ��� Conversation Loop (Mini-Hermes).

Full agent lifecycle: start session, tool-call turn updates engagement model,
session persisted, messages searchable.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.config.models import ProfileConfig
from praxis.core.agent import Agent
from praxis.engagement import GlossaryRepo
from praxis.storage.db import close_connection
from praxis.storage.repos.sessions import SessionRepo
from praxis.tools.models import ApprovalDecision
from praxis.tools.registry import ToolSpec, default_registry
from praxis.transport.base import Transport
from praxis.transport.models import (
    ChatRequest,
    ChatResponse,
    ProbeResult,
    StreamChunk,
    ToolCall,
    Usage,
)


class MockTransport(Transport):
    """Test transport with queued responses."""

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


class TestAgentUpdatesEngagementViaChat:
    """Full lifecycle: agent uses glossary_add_term tool to update engagement."""

    def test_full_lifecycle(self, eng: Path) -> None:
        transport = MockTransport()

        # LLM first calls glossary_add_term
        transport.queue_response(
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="glossary_add_term",
                    arguments_json='{"term":"invoice","definition":"A request for payment"}',
                )
            ]
        )
        # LLM then confirms
        transport.queue_response(text="Added 'invoice' to the glossary.")

        def approve(_spec: ToolSpec, _args: dict[str, object]) -> ApprovalDecision:
            return ApprovalDecision.APPROVE

        agent = Agent(
            profile=ProfileConfig(name="test"),
            engagement_path=eng,
            transport=transport,
            tool_registry=default_registry,
            approval_callback=approve,
        )

        sess_id = agent.start_session()
        resp = agent.turn("Please add 'invoice' to the glossary as 'A request for payment'.")

        # Agent responded with confirmation
        assert "added" in resp.content.lower() or "invoice" in resp.content.lower()

        # Engagement model was updated
        glossary = GlossaryRepo(eng).load()
        assert any(t.term == "invoice" for t in glossary.terms)

        # Session persisted
        db_path = eng / ".praxis" / "state" / "praxis.db"
        sessions = SessionRepo(db_path).list()
        assert sess_id in {s.id for s in sessions}

        # End session
        agent.end_session(summary="Test done")


class TestMaxIterationsCap:
    """Agent stops after max_tool_iterations."""

    def test_cap_prevents_infinite_loop(self, eng: Path) -> None:
        transport = MockTransport()
        for _ in range(20):
            transport.queue_response(
                tool_calls=[ToolCall(id="c1", name="current_time", arguments_json="{}")]
            )

        agent = Agent(
            profile=ProfileConfig(name="test"),
            engagement_path=eng,
            transport=transport,
            tool_registry=default_registry,
            max_tool_iterations=3,
        )
        agent.start_session()
        resp = agent.turn("Keep calling tools")

        assert resp.truncated
