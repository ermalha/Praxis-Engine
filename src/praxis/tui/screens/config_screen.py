"""ConfigScreen — inspect profile/model/project configuration."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from praxis.config.loader import load_engagement_config, load_global_config, load_profile
from praxis.config.profiles import get_active_profile_name
from praxis.errors import ConfigError


class ConfigScreen(Screen[None]):
    """Read-only configuration screen with setup guidance."""

    BINDINGS = [("r", "refresh", "Refresh")]

    def __init__(self, engagement_path: Path) -> None:
        super().__init__()
        self._engagement_path = engagement_path
        self.config_text = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="config-body")
        yield Footer()

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        profile_name = get_active_profile_name()
        global_cfg = load_global_config()
        try:
            profile = load_profile(profile_name)
        except ConfigError:
            profile = None
        engagement = load_engagement_config(self._engagement_path)
        model = (
            profile.model_aliases.get(profile.default_model_alias or "default")
            if profile is not None
            else None
        )
        model_lines = ["[bold]Model/Profile[/bold]"]
        active_profile = profile.name if profile is not None else profile_name
        model_lines.append(f"Active profile: {active_profile}")
        if model is not None:
            model_lines.extend(
                [
                    f"Provider: {model.provider.value}",
                    f"Model: {model.model}",
                    f"API key env: {model.api_key_env}",
                    f"Base URL: {model.base_url or '-'}",
                ]
            )
        else:
            model_lines.append("No default model configured.")
        self.config_text = "\n".join(
            [
                "[bold]Praxis Configuration[/bold]",
                f"PRAXIS_HOME/global default profile: {global_cfg.default_profile}",
                f"Engagement: {engagement.name}",
                f"Engagement path: {self._engagement_path}",
                "",
                *model_lines,
                "",
                "[bold]Setup guidance[/bold]",
                "OpenRouter:",
                "  export OPENROUTER_API_KEY=...",
                "  praxis profile create realworld --provider openrouter \\",
                "    --model anthropic/claude-sonnet-4 \\",
                "    --api-key-env OPENROUTER_API_KEY --set-default",
                "Standalone/local OpenAI-compatible:",
                "  praxis profile create local --provider openai_compat \\",
                "    --model <model> --api-key-env OPENAI_API_KEY --set-default",
                "  then edit the profile YAML to set base_url if needed.",
                "",
                "Future v0.2.x: this screen will add editable forms. In v0.2.0 it",
                "safely displays config and exact commands without collecting raw keys.",
            ]
        )
        self.query_one("#config-body", Static).update(self.config_text)

    def action_refresh(self) -> None:
        self._load()
