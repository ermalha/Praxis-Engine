"""PraxisApp — the main Textual application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from praxis.tui.screens.audit_screen import AuditScreen
from praxis.tui.screens.backlog_screen import BacklogScreen
from praxis.tui.screens.config_screen import ConfigScreen
from praxis.tui.screens.conversation_screen import ConversationScreen
from praxis.tui.screens.engagement_screen import EngagementScreen
from praxis.tui.screens.project_setup_screen import ProjectSetupScreen
from praxis.tui.screens.queue_screen import WorkQueueScreen

_SCREEN_MAP = {
    "queue": WorkQueueScreen,
    "conversation": ConversationScreen,
    "engagement": EngagementScreen,
    "audit": AuditScreen,
    "backlog": BacklogScreen,
    "config": ConfigScreen,
    "setup": ProjectSetupScreen,
}


class PraxisApp(App[None]):
    """Praxis TUI — the analyst's daily home."""

    TITLE = "Praxis"
    SUB_TITLE = "Agent-Led Business Analysis"

    CSS = """
    Screen {
        background: $surface;
    }
    """

    BINDINGS = [
        ("1", "switch_screen('queue')", "Queue"),
        ("2", "switch_screen('conversation')", "Chat"),
        ("3", "switch_screen('engagement')", "Engagement"),
        ("4", "switch_screen('audit')", "Audit"),
        ("5", "switch_screen('backlog')", "Backlog"),
        ("6", "switch_screen('config')", "Config"),
        ("7", "switch_screen('setup')", "Setup"),
        ("q", "quit", "Quit"),
        ("question_mark", "help", "Help"),
        ("w", "manual_wake", "Wake"),
    ]

    def __init__(
        self,
        engagement_path: Path,
        *,
        profile_name: str = "default",
        model_alias: str | None = None,
        initial_screen: str = "queue",
        chat_runtime_factory: object | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._engagement_path = engagement_path
        self._profile_name = profile_name
        self._model_alias = model_alias
        self._initial_screen = initial_screen
        self._chat_runtime_factory = chat_runtime_factory
        self._screens: dict[
            str,
            WorkQueueScreen
            | ConversationScreen
            | EngagementScreen
            | AuditScreen
            | BacklogScreen
            | ConfigScreen
            | ProjectSetupScreen,
        ] = {}

    def on_mount(self) -> None:
        # Install named screens
        self._screens = {
            "queue": WorkQueueScreen(self._engagement_path),
            "conversation": ConversationScreen(
                self._engagement_path,
                profile_name=self._profile_name,
                model_alias=self._model_alias,
                runtime_factory=self._chat_runtime_factory,
            ),
            "engagement": EngagementScreen(self._engagement_path),
            "audit": AuditScreen(self._engagement_path),
            "backlog": BacklogScreen(self._engagement_path),
            "config": ConfigScreen(self._engagement_path),
            "setup": ProjectSetupScreen(self._engagement_path),
        }
        for name, screen in self._screens.items():
            self.install_screen(screen, name)
        initial = self._initial_screen if self._initial_screen in self._screens else "queue"
        self.push_screen(initial)

    def action_switch_screen(self, screen_name: str) -> None:
        if screen_name in self._screens:
            self.switch_screen(screen_name)

    def action_help(self) -> None:
        self.notify(
            "Keys: 1=Queue 2=Chat 3=Engagement 4=Audit 5=Backlog 6=Config 7=Setup q=Quit r=Refresh w=Wake",
            title="Help",
        )

    def action_manual_wake(self) -> None:
        try:
            from praxis.config.loader import load_engagement_config, load_profile
            from praxis.core.orchestrator import Orchestrator
            from praxis.core.wake.models import WakeTrigger

            eng_config = load_engagement_config(self._engagement_path)
            profile = load_profile("default")
            orch = Orchestrator(
                agent=None,  # type: ignore[arg-type]
                profile=profile,
                engagement=eng_config,
                engagement_path=self._engagement_path,
            )
            report = orch.wake_once(trigger=WakeTrigger.MANUAL)
            self.notify(
                f"Wake complete: {len(report.tasks_executed)} tasks executed",
                title="Wake",
            )
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Wake failed: {exc}", severity="error")
