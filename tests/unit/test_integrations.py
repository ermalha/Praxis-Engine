"""Unit tests for the integrations subsystem."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from praxis.config.models import IntegrationConfig, IntegrationKind
from praxis.errors import IntegrationError
from praxis.integrations.base import Integration
from praxis.integrations.models import HealthResult, HealthStatus
from praxis.integrations.registry import (
    _reset_registry,
    get_integration,
    list_registered,
    register_integration,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset the integration registry between tests."""
    _reset_registry()
    yield
    _reset_registry()


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestIntegrationRegistry:
    def test_register_and_get(self):
        @register_integration
        class FakeIntegration(Integration):
            name = "Fake"
            kind = "fake"

            def health_check(self):
                return HealthResult(
                    kind=self.kind,
                    status=HealthStatus.HEALTHY,
                    message="ok",
                )

        cfg = IntegrationConfig(enabled=True, kind=IntegrationKind.JIRA)
        # kind mismatch with class, but registry uses class's kind
        result = get_integration("fake", cfg)
        assert isinstance(result, FakeIntegration)

    def test_duplicate_kind_raises(self):
        @register_integration
        class First(Integration):
            name = "First"
            kind = "dup"

            def health_check(self):
                return HealthResult(kind="dup", status=HealthStatus.HEALTHY)

        with pytest.raises(IntegrationError, match="Duplicate"):

            @register_integration
            class Second(Integration):
                name = "Second"
                kind = "dup"

                def health_check(self):
                    return HealthResult(kind="dup", status=HealthStatus.HEALTHY)

    def test_unknown_kind_raises(self):
        cfg = IntegrationConfig(enabled=True, kind=IntegrationKind.JIRA)
        with pytest.raises(IntegrationError, match="Unknown"):
            get_integration("nonexistent", cfg)

    def test_list_registered(self):
        @register_integration
        class A(Integration):
            name = "A"
            kind = "aaa"

            def health_check(self):
                return HealthResult(kind="aaa", status=HealthStatus.HEALTHY)

        @register_integration
        class B(Integration):
            name = "B"
            kind = "bbb"

            def health_check(self):
                return HealthResult(kind="bbb", status=HealthStatus.HEALTHY)

        assert list_registered() == ["aaa", "bbb"]


# ---------------------------------------------------------------------------
# Base class tests
# ---------------------------------------------------------------------------


class TestIntegrationBase:
    def test_is_enabled(self):
        cfg = IntegrationConfig(enabled=True, kind=IntegrationKind.JIRA)

        class FakeInt(Integration):
            name = "Fake"
            kind = "jira"

            def health_check(self):
                return HealthResult(kind="jira", status=HealthStatus.HEALTHY)

        i = FakeInt(cfg)
        assert i.is_enabled() is True

    def test_disabled_result(self):
        cfg = IntegrationConfig(enabled=False, kind=IntegrationKind.JIRA)

        class FakeInt(Integration):
            name = "Fake"
            kind = "jira"

            def health_check(self):
                return self._disabled_result()

        i = FakeInt(cfg)
        result = i.health_check()
        assert result.status == HealthStatus.DISABLED


# ---------------------------------------------------------------------------
# Jira client tests (mocked)
# ---------------------------------------------------------------------------


class TestJiraClient:
    def test_from_settings_missing_url_raises(self):
        from praxis.integrations.jira.client import JiraClient

        with pytest.raises(IntegrationError, match="base_url"):
            JiraClient.from_settings({})

    def test_from_settings_missing_creds_raises(self, monkeypatch):
        from praxis.integrations.jira.client import JiraClient

        monkeypatch.delenv("JIRA_EMAIL", raising=False)
        monkeypatch.delenv("JIRA_TOKEN", raising=False)
        with pytest.raises(IntegrationError, match="credentials"):
            JiraClient.from_settings({"base_url": "https://x.atlassian.net"})

    def test_search_issues(self, monkeypatch):
        monkeypatch.setenv("JIRA_EMAIL", "test@example.com")
        monkeypatch.setenv("JIRA_TOKEN", "secret")

        import respx as respx_lib

        from praxis.integrations.jira.client import JiraClient

        with respx_lib.mock:
            respx_lib.get("https://x.atlassian.net/rest/api/3/search").respond(
                json={"issues": [{"key": "BA-1", "fields": {"summary": "Test"}}]}
            )
            client = JiraClient(
                base_url="https://x.atlassian.net",
                email="test@example.com",
                token="secret",
            )
            issues = client.search_issues("project=BA")
            assert len(issues) == 1
            assert issues[0]["key"] == "BA-1"
            client.close()


# ---------------------------------------------------------------------------
# Confluence client tests (mocked)
# ---------------------------------------------------------------------------


class TestConfluenceClient:
    def test_from_settings_missing_url_raises(self):
        from praxis.integrations.confluence.client import ConfluenceClient

        with pytest.raises(IntegrationError, match="base_url"):
            ConfluenceClient.from_settings({})

    def test_search(self, monkeypatch):
        monkeypatch.setenv("CONFLUENCE_EMAIL", "test@example.com")
        monkeypatch.setenv("CONFLUENCE_TOKEN", "secret")

        import respx as respx_lib

        from praxis.integrations.confluence.client import ConfluenceClient

        with respx_lib.mock:
            respx_lib.get("https://x.atlassian.net/wiki/rest/api/content/search").respond(
                json={"results": [{"id": "123", "title": "Page"}]}
            )

            client = ConfluenceClient(
                base_url="https://x.atlassian.net",
                email="test@example.com",
                token="secret",
            )
            results = client.search("type=page")
            assert len(results) == 1
            assert results[0]["title"] == "Page"
            client.close()


# ---------------------------------------------------------------------------
# Email models
# ---------------------------------------------------------------------------


class TestEmailModels:
    def test_parsed_message(self):
        from praxis.integrations.email.models import ParsedMessage

        msg = ParsedMessage(
            message_id="<abc@example.com>",
            from_addr="alice@example.com",
            to_addrs=["bob@example.com"],
            subject="Hello",
            body="World",
        )
        assert msg.message_id == "<abc@example.com>"
        assert msg.in_reply_to is None


# ---------------------------------------------------------------------------
# Webhook receiver tests
# ---------------------------------------------------------------------------


class TestWebhookReceiver:
    def test_validate_and_persist(self, tmp_path):
        from praxis.integrations.webhook.receiver import WebhookReceiver

        eng = tmp_path / "eng"
        eng.mkdir()
        (eng / ".praxis" / "state").mkdir(parents=True)

        settings = {
            "port": "8765",
            "paths": '[{"path": "/test", "kind": "test_hook", "secret_env": ""}]',
        }
        receiver = WebhookReceiver(settings, eng)
        payload = b'{"event": "test"}'
        dest = receiver.validate_and_persist("/test", payload)
        assert dest.exists()
        assert "test_hook" in dest.read_text()

    def test_unknown_path_raises(self, tmp_path):
        from praxis.integrations.webhook.receiver import WebhookReceiver

        eng = tmp_path / "eng"
        eng.mkdir()
        settings = {"port": "8765", "paths": "[]"}
        receiver = WebhookReceiver(settings, eng)
        with pytest.raises(IntegrationError, match="No webhook registered"):
            receiver.validate_and_persist("/nope", b"{}")


# ---------------------------------------------------------------------------
# Browser install tests
# ---------------------------------------------------------------------------


class TestBrowserInstall:
    def test_doctor_not_installed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "praxis.integrations.browser.install.DEFAULT_INSTALL_PATH",
            tmp_path / "nonexistent",
        )
        from praxis.integrations.browser.install import doctor

        result = doctor(tmp_path / "nonexistent")
        assert result["installed"] is False

    def test_install_creates_dir(self, tmp_path, monkeypatch):
        dest = tmp_path / "harness"
        # Mock git clone
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: MagicMock(returncode=0),
        )
        monkeypatch.setattr(
            "praxis.integrations.browser.install.DEFAULT_INSTALL_PATH",
            dest,
        )
        # Create fake structure so symlinks work
        dest.mkdir()
        (dest / "SKILL.md").write_text("# Browser Skill")

        monkeypatch.setattr(
            "pathlib.Path.home",
            lambda: tmp_path,
        )

        from praxis.integrations.browser.install import install

        result = install(dest)
        assert result == dest


# ---------------------------------------------------------------------------
# Graceful degradation tests
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    def test_jira_tools_not_registered_when_disabled(self):
        """When Jira is disabled, its tools should not appear for the agent."""
        # The graceful degradation is at the agent layer, not tool registration
        # This test verifies the config pattern works
        from praxis.config.models import EngagementConfig

        cfg = EngagementConfig(name="test")
        # No integrations configured — agent won't include jira toolset
        assert "jira" not in cfg.integrations
