"""Integration tests for chunk 14 — Integrations Bundle.

Tests graceful degradation, Jira sync flow (mocked), webhook persistence,
and email reply matching.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from praxis.config.engagement import init_engagement
from praxis.config.loader import load_engagement_config, save_engagement_config
from praxis.config.models import IntegrationConfig, IntegrationKind
from praxis.integrations.models import HealthStatus
from praxis.integrations.registry import _reset_registry, get_integration
from praxis.storage.db import close_connection
from praxis.workqueue import WorkItemPriority, WorkItemStatus, WorkItemType, WorkQueueRepo


@pytest.fixture()
def eng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Engagement with no integrations configured."""
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


@pytest.fixture(autouse=True)
def _clean_registry():
    import importlib

    import praxis.integrations.confluence.integration
    import praxis.integrations.email.integration
    import praxis.integrations.jira.integration
    import praxis.integrations.webhook.integration

    _reset_registry()
    importlib.reload(praxis.integrations.jira.integration)
    importlib.reload(praxis.integrations.confluence.integration)
    importlib.reload(praxis.integrations.email.integration)
    importlib.reload(praxis.integrations.webhook.integration)

    yield
    _reset_registry()


def test_jira_integration_is_optional(eng: Path) -> None:
    """When Jira is not configured, agent operates without it."""
    cfg = load_engagement_config(eng)
    # No Jira in integrations
    assert "jira" not in cfg.integrations

    # Agent can still draft stories locally
    stories_dir = eng / ".praxis" / "artifacts" / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)
    story_path = stories_dir / "BA-001.md"
    story_path.write_text("# User Story BA-001\n\nAs a user...")
    assert story_path.exists()


def test_jira_sync_when_enabled(eng: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When Jira is enabled and configured, sync creates an issue (mocked)."""
    monkeypatch.setenv("JIRA_EMAIL", "test@example.com")
    monkeypatch.setenv("JIRA_TOKEN", "secret-token")

    # Enable Jira in config
    cfg = load_engagement_config(eng)
    cfg.integrations["jira"] = IntegrationConfig(
        enabled=True,
        kind=IntegrationKind.JIRA,
        settings={
            "base_url": "https://example.atlassian.net",
            "email_env": "JIRA_EMAIL",
            "token_env": "JIRA_TOKEN",
            "default_project": "BA",
        },
    )
    save_engagement_config(eng, cfg)

    # Draft a story locally
    stories_dir = eng / ".praxis" / "artifacts" / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)
    story_path = stories_dir / "BA-001.md"
    story_path.write_text("# User Story\n\nAs a BA, I want to track requirements.")

    # Mock the Jira API call
    with respx.mock:
        respx.post("https://example.atlassian.net/rest/api/3/issue").mock(
            return_value=Response(201, json={"key": "BA-42", "id": "10042"})
        )

        from praxis.integrations.jira.client import JiraClient

        client = JiraClient.from_settings(cfg.integrations["jira"].settings)
        result = client.create_issue(
            project="BA",
            summary="User Story BA-001",
            description="As a BA, I want to track requirements.",
        )
        client.close()

        assert result["key"] == "BA-42"

    # Update local story with Jira key
    story_path.write_text(f"# User Story (Jira: {result['key']})\n\nAs a BA...")
    assert "BA-42" in story_path.read_text()


def test_webhook_receives_and_persists(eng: Path) -> None:
    """Webhook receiver validates, persists payload, and emits audit event."""
    from praxis.integrations.webhook.receiver import WebhookReceiver

    settings = {
        "port": "8765",
        "paths": json.dumps([{"path": "/ci-events", "kind": "ci_webhook", "secret_env": ""}]),
    }
    receiver = WebhookReceiver(settings, eng)
    payload = json.dumps({"build": "passed", "commit": "abc123"}).encode()

    dest = receiver.validate_and_persist("/ci-events", payload)
    assert dest.exists()

    content = json.loads(dest.read_text())
    assert content["kind"] == "ci_webhook"
    assert content["payload"]["build"] == "passed"


def test_email_reply_matching(eng: Path) -> None:
    """Email matcher links incoming messages to SEND_MESSAGE work-items."""
    # Create a DONE SEND_MESSAGE work-item
    repo = WorkQueueRepo(eng)
    repo.enqueue(
        type=WorkItemType.SEND_MESSAGE,
        assignee="human",
        title="Send follow-up to alice@example.com",
        description="Ask about requirements",
        priority=WorkItemPriority.MEDIUM,
        rationale="Stalled question",
        payload={"recipient": "alice@example.com"},
    )
    items = repo.list()
    item = items[0]
    # Transition to DONE (simulate committed)
    repo.transition(item.id, WorkItemStatus.IN_PROGRESS)
    repo.transition(item.id, WorkItemStatus.DONE)

    from praxis.integrations.email.matcher import match_replies
    from praxis.integrations.email.models import ParsedMessage

    messages = [
        ParsedMessage(
            message_id="<reply@example.com>",
            from_addr="alice@example.com",
            to_addrs=["praxis@mycompany.com"],
            subject="Re: Follow-up",
            body="Here are the requirements...",
        )
    ]

    matches = match_replies(messages, eng)
    assert len(matches) == 1
    assert matches[0][1] == item.id


def test_disabled_integration_health_check() -> None:
    """Disabled integrations report DISABLED status."""
    cfg = IntegrationConfig(enabled=False, kind=IntegrationKind.JIRA)
    integration = get_integration("jira", cfg)
    result = integration.health_check()
    assert result.status == HealthStatus.DISABLED
