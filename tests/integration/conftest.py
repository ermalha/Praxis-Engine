"""Shared fixtures for integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.config.models import ModelConfig, Provider
from praxis.config.profiles import create_profile, save_profile
from praxis.transport import ChatRequest, ChatResponse


class StubTransport:
    """Fake transport that records incoming requests and returns canned text.

    Used by integration tests that want to exercise CLI flow up to the LLM
    call without making a real network request. Inspect ``requests`` to
    assert what would have been sent.
    """

    name = "stub"

    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        return ChatResponse(content="stub-response", finish_reason="stop")


@pytest.fixture()
def stub_transport(monkeypatch: pytest.MonkeyPatch) -> StubTransport:
    """Replace ``make_transport`` in every CLI module that imports it.

    Patches each command module's own binding (since modules use
    ``from ... import make_transport``).
    """
    stub = StubTransport()

    def fake_make_transport(_model_config: object) -> StubTransport:
        return stub

    for module_path in (
        "praxis.cli.ask_cmd.make_transport",
        "praxis.cli.doctor_cmd.make_transport",
        "praxis.cli.check_cmd.make_transport",
        "praxis.cli.artifact_cmd.make_transport",
        "praxis.cli.elicit_cmd.make_transport",
    ):
        monkeypatch.setattr(module_path, fake_make_transport)
    return stub


@pytest.fixture()
def realworld_profile(tmp_home: Path) -> str:
    """Create a profile with a default model so commands can resolve transport.

    The transport is stubbed via :func:`stub_transport`, so the model and
    key-env are placeholders. The profile is auto-set as the global active
    default by ``create_profile`` when it is the only profile.
    """
    profile = create_profile("realworld")
    profile.model_aliases["default"] = ModelConfig(
        provider=Provider.OPENAI,
        model="gpt-test",
        api_key_env="OPENAI_API_KEY",
    )
    profile.default_model_alias = "default"
    save_profile(profile)
    # create_profile doesn't auto-set the global default; do it here so commands
    # that resolve the active profile pick this one up.
    from praxis.config.loader import save_global_config
    from praxis.config.models import GlobalConfig

    save_global_config(GlobalConfig(default_profile="realworld"))
    return "realworld"
