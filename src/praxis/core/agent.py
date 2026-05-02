"""The Praxis Agent — turn-based conversation with tool calling."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import structlog

from praxis.audit import emit
from praxis.config.models import EngagementConfig, ProfileConfig
from praxis.skills import SkillRegistry
from praxis.tools.context import ToolContext
from praxis.tools.executor import execute_tool_calls
from praxis.tools.models import ApprovalDecision
from praxis.tools.registry import ToolRegistry, ToolSpec
from praxis.transport.base import Transport, assemble_response
from praxis.transport.models import (
    ChatRequest,
    Message,
    Usage,
)

from .models import AgentResponse, StreamEvent
from .prompt import build_system_prompt
from .session import (
    create_session,
    end_session,
    load_session_messages,
    persist_message,
)

logger = structlog.get_logger()

_DEFAULT_MAX_ITERATIONS = 25


class Agent:
    """Turn-based conversational agent with tool calling."""

    def __init__(
        self,
        *,
        profile: ProfileConfig,
        engagement: EngagementConfig | None = None,
        engagement_path: Path | None = None,
        transport: Transport,
        tool_registry: ToolRegistry,
        skill_registry: SkillRegistry | None = None,
        approval_callback: Callable[[ToolSpec, dict[str, object]], ApprovalDecision] | None = None,
        max_tool_iterations: int = _DEFAULT_MAX_ITERATIONS,
        enabled_toolsets: set[str] | None = None,
        model: str = "default",
    ) -> None:
        self._profile = profile
        self._engagement = engagement
        self._engagement_path = engagement_path
        self._transport = transport
        self._tool_registry = tool_registry
        self._skill_registry = skill_registry
        self._approval_callback = approval_callback
        self._max_iterations = max_tool_iterations
        self._model = model

        self._enabled_toolsets = enabled_toolsets or {
            "engagement",
            "agent",
            "debug",
            "skills",
        }

        self._session_id: str | None = None
        self._msg_seq = 0  # monotonically increasing message sequence
        self._db_path: Path | None = None

        if engagement_path is not None:
            self._db_path = engagement_path / ".praxis" / "state" / "praxis.db"

        self._system_prompt = build_system_prompt(
            profile=profile,
            engagement=engagement,
            engagement_path=engagement_path,
            skill_registry=skill_registry,
        )

    @property
    def session_id(self) -> str | None:
        """Current session ID, or None if no session is active."""
        return self._session_id

    def start_session(self, parent_id: str | None = None) -> str:
        """Start a new session. Returns the session ID."""
        if self._db_path is None:
            msg = "No engagement active — cannot persist sessions"
            raise ValueError(msg)

        session = create_session(
            self._db_path,
            self._profile.name,
            parent_id=parent_id,
        )
        self._session_id = session.id
        self._msg_seq = 0
        emit(
            "session.started",
            component="agent",
            subject_id=session.id,
        )
        return session.id

    def turn(
        self,
        user_input: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AgentResponse:
        """Execute a full turn (non-streaming)."""
        events = list(self.stream_turn(user_input, cancel_event=cancel_event))
        # Collect final response from done event
        text_parts: list[str] = []
        tool_count = 0
        truncated = False
        for ev in events:
            if ev.type == "text_delta" and ev.text:
                text_parts.append(ev.text)
            elif ev.type == "tool_result":
                tool_count += 1
            elif ev.type == "done" and ev.status == "truncated":
                truncated = True

        return AgentResponse(
            content="".join(text_parts),
            tool_call_count=tool_count,
            session_id=self._session_id or "",
            truncated=truncated,
        )

    def _next_seq(self) -> int:
        """Return the next message sequence number."""
        self._msg_seq += 1
        return self._msg_seq

    def stream_turn(
        self,
        user_input: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Iterator[StreamEvent]:
        """Execute a turn, yielding streaming events."""
        if self._session_id is None:
            msg = "No session active — call start_session() first"
            raise ValueError(msg)

        emit(
            "turn.started",
            component="agent",
            subject_id=self._session_id,
        )

        # 1. Persist user message
        if self._db_path is not None:
            persist_message(
                self._db_path,
                session_id=self._session_id,
                turn=self._next_seq(),
                role="user",
                content=user_input,
            )

        # 2. Build conversation history
        messages = self._build_messages(user_input)

        # 3. Build tool definitions
        tool_defs = self._tool_registry.to_definitions(self._enabled_toolsets)

        # 4. Iteration loop
        iteration = 0
        total_usage = Usage()

        while iteration < self._max_iterations:
            iteration += 1

            if cancel_event and cancel_event.is_set():
                yield StreamEvent(type="done", status="cancelled")
                return

            # Call transport
            request = ChatRequest(
                model=self._model,
                messages=messages,
                tools=tool_defs if tool_defs else None,
                stream=True,
            )

            response = assemble_response(
                self._transport.chat_stream(request, cancel_event=cancel_event)
            )

            # Accumulate usage
            ru = response.usage
            total_usage = Usage(
                prompt_tokens=total_usage.prompt_tokens + ru.prompt_tokens,
                completion_tokens=total_usage.completion_tokens + ru.completion_tokens,
                cache_read_tokens=total_usage.cache_read_tokens + ru.cache_read_tokens,
                cache_write_tokens=total_usage.cache_write_tokens + ru.cache_write_tokens,
            )

            # Check if model wants tool calls
            has_tool_calls = response.tool_calls and response.finish_reason in (
                "tool_use",
                "tool_calls",
                "stop",
            )

            if has_tool_calls and response.tool_calls:
                # Yield tool call start events
                for tc in response.tool_calls:
                    yield StreamEvent(
                        type="tool_call_start",
                        tool_name=tc.name,
                        tool_call_id=tc.id,
                    )

                # Persist assistant message with tool calls
                tc_json = json.dumps([tc.model_dump(mode="json") for tc in response.tool_calls])
                if self._db_path is not None:
                    persist_message(
                        self._db_path,
                        session_id=self._session_id,
                        turn=self._next_seq(),
                        role="assistant",
                        content=response.content,
                        tool_calls_json=tc_json,
                    )

                # Execute tool calls
                ctx = self._build_tool_context()
                results = execute_tool_calls(
                    response.tool_calls,
                    ctx,
                    approval_callback=self._approval_callback,
                    cancel_event=cancel_event,
                    registry=self._tool_registry,
                )

                # Yield tool results and persist
                for result in results:
                    yield StreamEvent(
                        type="tool_result",
                        tool_call_id=result.tool_call_id,
                        tool_result=result.content,
                        is_error=result.is_error,
                    )
                    if self._db_path is not None:
                        persist_message(
                            self._db_path,
                            session_id=self._session_id,
                            turn=self._next_seq(),
                            role="tool",
                            content=result.content,
                        )

                # Add assistant and tool messages to conversation
                messages.append(
                    Message(
                        role="assistant",
                        content=response.content or "",
                        tool_calls=response.tool_calls,
                    )
                )
                for result in results:
                    messages.append(
                        Message(
                            role="tool",
                            content=result.content,
                            tool_call_id=result.tool_call_id,
                        )
                    )

                continue  # Next iteration

            # No tool calls — final text response
            if response.content:
                yield StreamEvent(type="text_delta", text=response.content)

            # Persist final assistant message
            if self._db_path is not None:
                persist_message(
                    self._db_path,
                    session_id=self._session_id,
                    turn=self._next_seq(),
                    role="assistant",
                    content=response.content,
                )

            content_hash = hashlib.sha256(response.content.encode()).hexdigest()[:16]
            emit(
                "agent.message_sent",
                component="agent",
                subject_id=self._session_id,
                content_hash=content_hash,
            )

            emit(
                "turn.completed",
                component="agent",
                subject_id=self._session_id,
                turn=self._msg_seq,
                iterations=iteration,
            )

            yield StreamEvent(type="done", status="complete")
            return

        # Max iterations reached
        logger.warning(
            "agent.max_iterations",
            session_id=self._session_id,
            max=self._max_iterations,
        )
        emit(
            "turn.completed",
            component="agent",
            subject_id=self._session_id,
            turn=self._msg_seq,
            iterations=iteration,
            truncated=True,
        )
        yield StreamEvent(type="done", status="truncated")

    def end_session(self, summary: str | None = None) -> None:
        """End the current session."""
        if self._session_id is None:
            return
        if self._db_path is not None:
            end_session(self._db_path, self._session_id, summary=summary)
        emit(
            "session.ended",
            component="agent",
            subject_id=self._session_id,
        )
        self._session_id = None

    def _build_messages(self, user_input: str) -> list[Message]:
        """Build the message list from session history + current input."""
        messages: list[Message] = [
            Message(role="system", content=self._system_prompt),
        ]

        # Load history from DB
        if self._db_path is not None and self._session_id is not None:
            history = load_session_messages(self._db_path, self._session_id)
            # Exclude the user message we just persisted (it's the current input)
            # and any system messages
            for msg in history:
                if msg.role != "system":
                    messages.append(msg)

        # Current user input (already persisted, but we need it in the message list)
        # It's already in history from persist_message above, but if history
        # loading included it, we don't need to add again.
        # Check if last message is already this user input
        if not messages or messages[-1].content != user_input:
            messages.append(Message(role="user", content=user_input))

        return messages

    def _build_tool_context(self) -> ToolContext:
        """Build a ToolContext for tool execution."""
        return ToolContext(
            profile=self._profile,
            engagement=self._engagement,
            engagement_path=self._engagement_path,
            audit=emit,
        )
