"""D-057 — TUI manual wake honours the selected profile.

Closes the Hermes review's "most concrete code-level fix": the TUI's
``action_manual_wake`` previously called ``load_profile("default")``
regardless of the profile the app was launched with, so
``praxis tui --profile alt-profile`` + ``w`` keybind silently woke
under the wrong profile. This guards against that regression.

Also pinned here: ``Orchestrator(agent=None, ...)`` constructs cleanly
without the ``# type: ignore[arg-type]`` smell — wake handlers in v0.x
are rule-based and don't need an agent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.config.engagement import init_engagement
from praxis.config.loader import load_engagement_config
from praxis.config.models import ModelConfig, Provider
from praxis.config.profiles import create_profile, save_profile
from praxis.core.orchestrator import Orchestrator


def _create_alt_profile() -> str:
    """Helper: create a non-default profile so the test can select it."""
    profile = create_profile("alt-profile")
    profile.model_aliases["default"] = ModelConfig(
        provider=Provider.OPENAI,
        model="gpt-test",
        api_key_env="OPENAI_API_KEY",
    )
    profile.default_model_alias = "default"
    save_profile(profile)
    return "alt-profile"


class TestManualWakeProfile:
    def test_manual_wake_uses_selected_profile_not_default(
        self,
        tmp_engagement: Path,
        tmp_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Manual wake under a non-default profile must use that profile.

        ``PraxisApp(profile_name="alt-profile")`` + the ``w`` keybind must
        result in ``load_profile("alt-profile")``. Previously the action
        hard-coded ``"default"``, regardless of the configured profile.
        """
        _create_alt_profile()
        init_engagement(tmp_engagement, "Test")

        # Spy on the loader's load_profile — the TUI action does
        # ``from praxis.config.loader import load_profile`` at call time, so
        # patching the source module catches the lookup.
        captured: list[str] = []
        import praxis.config.loader as loader_module

        real_load_profile = loader_module.load_profile

        def spy(name: str) -> object:
            captured.append(name)
            return real_load_profile(name)

        monkeypatch.setattr(loader_module, "load_profile", spy)

        from praxis.tui.app import PraxisApp

        app = PraxisApp(
            engagement_path=tmp_engagement,
            profile_name="alt-profile",
            initial_screen="queue",
        )
        # ``self.notify`` requires a running Textual app context. Replace it
        # with a no-op so we can exercise the action directly without spinning
        # up the full Pilot driver — the assertion is about ``load_profile``,
        # not the toast.
        monkeypatch.setattr(app, "notify", lambda *a, **kw: None)

        app.action_manual_wake()

        assert "alt-profile" in captured, (
            f"action_manual_wake did not call load_profile('alt-profile'); "
            f"captured calls were: {captured!r}"
        )
        assert "default" not in captured, (
            "action_manual_wake still calls load_profile('default') — the v0.3.x bug regressed."
        )


class TestOrchestratorOptionalAgent:
    def test_constructs_with_none_agent_no_type_ignore(
        self,
        tmp_engagement: Path,
        tmp_home: Path,
    ) -> None:
        """``Orchestrator(agent=None, ...)`` constructs without ``# type: ignore``.

        Wake handlers are rule-based today; the agent field is forward-compat
        for inline-LLM wake (D-059 + later). This unit test only proves the
        runtime construction; mypy's strict pass on master proves the type
        story (the previous ``# type: ignore[arg-type]`` comments are gone).
        """
        init_engagement(tmp_engagement, "Test")
        profile = _create_alt_profile()
        from praxis.config.loader import load_profile

        eng_config = load_engagement_config(tmp_engagement)
        loaded = load_profile(profile)

        orch = Orchestrator(
            agent=None,
            profile=loaded,
            engagement=eng_config,
            engagement_path=tmp_engagement,
        )
        assert orch.engagement_path == tmp_engagement
