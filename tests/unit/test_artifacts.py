"""Tests for state-grounded artifact generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.artifacts import ArtifactResult, generate_artifact, list_artifacts
from praxis.config.engagement import init_engagement
from praxis.config.models import ProfileConfig
from praxis.engagement.repos.assumptions import AssumptionsConstraintsRepo
from praxis.engagement.repos.decisions import DecisionRepo
from praxis.engagement.repos.glossary import GlossaryRepo
from praxis.engagement.repos.questions import OpenQuestionsRepo
from praxis.engagement.repos.risks import RiskRepo
from praxis.engagement.repos.stakeholders import StakeholderRepo
from praxis.storage.db import close_connection
from praxis.transport import ChatRequest, ChatResponse


class FakeTransport:
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        prompt = request.messages[-1].content
        assert isinstance(prompt, str)
        assert "Northstar Digital Loan Intake" in prompt
        assert "Maria Chen" in prompt
        assert "Personal loans only" in prompt
        return ChatResponse(content="# MVP Scope Brief\n\nNorthstar Digital Loan Intake scope.")


@pytest.fixture()
def eng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    praxis_home = tmp_path / ".praxis-home"
    praxis_home.mkdir()
    monkeypatch.setenv("PRAXIS_HOME", str(praxis_home))
    monkeypatch.setenv("HOME", str(tmp_path))

    eng_dir = tmp_path / "engagement"
    eng_dir.mkdir()
    init_engagement(eng_dir, "Northstar Digital Loan Intake")
    StakeholderRepo(eng_dir).add("Maria Chen", "VP of Lending")
    GlossaryRepo(eng_dir).add_term("Member", "Credit union customer")
    OpenQuestionsRepo(eng_dir).open("What fields are required?", "Needed for MVP", priority="high")
    AssumptionsConstraintsRepo(eng_dir).add_constraint(
        "Must comply with GLBA", "regulatory", source="business case"
    )
    RiskRepo(eng_dir).add("Vendor API", "Vendor API may be limited", "medium", "high")
    DecisionRepo(eng_dir).create(
        "Personal loans only",
        "MVP scope",
        "Personal loans only for MVP",
        "Auto loans deferred",
    )
    yield eng_dir
    close_connection(eng_dir / ".praxis" / "state" / "praxis.db")


def test_generate_artifact_loads_state_and_writes_file(eng: Path) -> None:
    transport = FakeTransport()

    result = generate_artifact(
        engagement_path=eng,
        profile=ProfileConfig(name="default"),
        model="fake-model",
        transport=transport,
        artifact_kind="scope-brief",
        prompt="Create an MVP scope brief using known facts.",
        output_dir="reports",
    )

    assert isinstance(result, ArtifactResult)
    assert result.path.exists()
    assert result.path.is_absolute()
    assert result.content.startswith("# MVP Scope Brief")
    assert result.artifact_kind == "scope-brief"
    assert "Northstar" in result.path.read_text(encoding="utf-8")
    assert transport.requests


def test_list_artifacts_finds_generated_files(eng: Path) -> None:
    path = eng / ".praxis" / "artifacts" / "reports" / "one.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# One", encoding="utf-8")

    artifacts = list_artifacts(eng)

    assert any(item.path == path.resolve() for item in artifacts)
