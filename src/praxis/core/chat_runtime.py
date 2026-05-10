"""Shared chat runtime for CLI and TUI conversation surfaces."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from praxis.config.loader import load_engagement_config, load_profile, resolve_model_config
from praxis.config.models import EngagementConfig, ProfileConfig
from praxis.core.agent import Agent
from praxis.core.models import StreamEvent
from praxis.skills import SkillRegistry
from praxis.tools.approval import ApprovalDecision
from praxis.tools.registry import ToolSpec, default_registry
from praxis.transport import Transport, make_transport


@dataclass(frozen=True)
class SlashResult:
    """Result from handling a slash command."""

    continue_session: bool
    text: str


ApprovalCallback = Callable[[ToolSpec, dict[str, object]], ApprovalDecision]
AgentFactory = Callable[..., Agent]


class ChatRuntime:
    """Reusable conversation runtime shared by CLI chat and TUI chat."""

    def __init__(
        self,
        *,
        profile: ProfileConfig,
        engagement_path: Path | None,
        engagement: EngagementConfig | None,
        model: str,
        transport: Transport | None,
        agent: Any,
    ) -> None:
        self.profile = profile
        self.engagement_path = engagement_path
        self.engagement = engagement
        self.model = model
        self.transport = transport
        self.agent = agent
        self.session_id: str | None = None
        self.db_path = (
            engagement_path / ".praxis" / "state" / "praxis.db"
            if engagement_path is not None
            else None
        )

    @classmethod
    def create(
        cls,
        *,
        profile_name: str = "default",
        engagement_path: Path | None,
        model_alias: str | None = None,
        approval_callback: ApprovalCallback | None = None,
        transport: Transport | None = None,
        agent_factory: AgentFactory | None = None,
    ) -> ChatRuntime:
        """Create a runtime by resolving profile, engagement, model, tools, and skills."""
        engagement = load_engagement_config(engagement_path) if engagement_path is not None else None
        profile = load_profile(profile_name)
        model_config = resolve_model_config(profile, engagement, model_alias)
        resolved_transport = transport or make_transport(model_config)
        skill_registry = SkillRegistry(engagement_path=engagement_path)
        factory = agent_factory or Agent
        agent = factory(
            profile=profile,
            engagement=engagement,
            engagement_path=engagement_path,
            transport=resolved_transport,
            tool_registry=default_registry,
            skill_registry=skill_registry,
            approval_callback=approval_callback,
            model=model_config.model,
        )
        return cls(
            profile=profile,
            engagement_path=engagement_path,
            engagement=engagement,
            model=model_config.model,
            transport=resolved_transport,
            agent=agent,
        )

    def start(self) -> str:
        """Start a session if needed and return its ID."""
        if self.session_id is None:
            self.session_id = str(self.agent.start_session())
        return self.session_id

    def close(self, summary: str | None = None) -> None:
        """End the active session if one was started."""
        if self.session_id is not None:
            self.agent.end_session(summary=summary)
            self.session_id = None

    def stream_turn(self, user_input: str) -> Iterable[StreamEvent]:
        """Stream a single agent turn, starting the session lazily."""
        self.start()
        yield from self.agent.stream_turn(user_input)

    def handle_slash(self, command_text: str) -> SlashResult:
        """Handle chat slash commands and return renderable text."""
        parts = command_text.strip().split(None, 1)
        command = parts[0].lower() if parts else ""

        if command == "/exit":
            return SlashResult(continue_session=False, text="Session exit requested.")

        if command == "/new":
            self.close()
            sid = self.start()
            return SlashResult(continue_session=True, text=f"New session: {sid}")

        if command == "/sessions":
            if self.db_path is None:
                return SlashResult(True, "No engagement session store is available.")
            from praxis.core.session import list_sessions

            sessions = list_sessions(self.db_path)
            if not sessions:
                return SlashResult(True, "No sessions.")
            lines = []
            for session in sessions:
                status = "ended" if session.ended_at else "active"
                summary = f" — {session.summary}" if session.summary else ""
                lines.append(f"  [{status}] {session.id[:12]}…{summary}")
            return SlashResult(True, "\n".join(lines))

        if command == "/skills":
            tools = default_registry.list_tools(toolset="skills")
            if not tools:
                return SlashResult(True, "No skill tools.")
            return SlashResult(
                True,
                "\n".join(f"  - {tool.name}: {tool.description}" for tool in tools),
            )

        if command == "/tools":
            lines = []
            for tool in default_registry.list_tools():
                tag = " [dangerous]" if tool.dangerous else ""
                lines.append(f"  - {tool.name} ({tool.toolset}){tag}")
            return SlashResult(True, "\n".join(lines))

        if command == "/help":
            return SlashResult(
                True,
                "/exit  — end session and quit\n"
                "/new   — start a new session\n"
                "/sessions — list recent sessions\n"
                "/skills — list active skills\n"
                "/tools  — list available tools\n"
                "/help   — show this help",
            )

        return SlashResult(True, f"Unknown command: {command}")
