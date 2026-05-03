"""Jira REST API client — wraps httpx calls to the Jira Cloud/Server API."""

from __future__ import annotations

import os
from typing import Any

import httpx

from praxis.errors import IntegrationError


class JiraClient:
    """Thin wrapper around the Jira REST v3 API.

    Uses ``httpx`` directly rather than ``atlassian-python-api`` so we keep
    the dependency optional and have full control over request shaping.
    """

    def __init__(
        self,
        base_url: str,
        email: str,
        token: str,
        *,
        timeout: int = 30,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=f"{self._base}/rest/api/3",
            auth=(email, token),
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    @classmethod
    def from_settings(cls, settings: dict[str, str]) -> JiraClient:
        """Create a client from integration settings dict."""
        base_url = settings.get("base_url", "")
        if not base_url:
            raise IntegrationError("Jira base_url not configured", kind="jira")
        email_env = settings.get("email_env", "JIRA_EMAIL")
        token_env = settings.get("token_env", "JIRA_TOKEN")
        email = os.environ.get(email_env, "")
        token = os.environ.get(token_env, "")
        if not email or not token:
            raise IntegrationError(
                f"Jira credentials missing: set {email_env} and {token_env}",
                kind="jira",
            )
        return cls(base_url=base_url, email=email, token=token)

    def search_issues(self, jql: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search issues using JQL."""
        resp = self._client.get(
            "/search",
            params={"jql": jql, "maxResults": limit},
        )
        resp.raise_for_status()
        return resp.json().get("issues", [])

    def get_issue(self, key: str) -> dict[str, Any]:
        """Fetch a single issue by key."""
        resp = self._client.get(f"/issue/{key}")
        resp.raise_for_status()
        return resp.json()

    def list_projects(self) -> list[dict[str, Any]]:
        """List all accessible projects."""
        resp = self._client.get("/project")
        resp.raise_for_status()
        return resp.json()

    def get_sprint_issues(self, sprint_id: int) -> list[dict[str, Any]]:
        """Get issues for a sprint (via JQL)."""
        return self.search_issues(f"sprint = {sprint_id}")

    def create_issue(
        self,
        project: str,
        summary: str,
        description: str,
        issuetype: str = "Story",
        **extra_fields: Any,
    ) -> dict[str, Any]:
        """Create an issue. Returns the created issue payload."""
        fields: dict[str, Any] = {
            "project": {"key": project},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            },
            "issuetype": {"name": issuetype},
            **extra_fields,
        }
        resp = self._client.post("/issue", json={"fields": fields})
        resp.raise_for_status()
        return resp.json()

    def update_issue(self, key: str, fields: dict[str, Any]) -> None:
        """Update issue fields."""
        resp = self._client.put(f"/issue/{key}", json={"fields": fields})
        resp.raise_for_status()

    def add_comment(self, key: str, body: str) -> dict[str, Any]:
        """Add a comment to an issue."""
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body}],
                    }
                ],
            },
        }
        resp = self._client.post(f"/issue/{key}/comment", json=payload)
        resp.raise_for_status()
        return resp.json()

    def transition_issue(self, key: str, transition_id: str) -> None:
        """Transition an issue to a new status."""
        resp = self._client.post(
            f"/issue/{key}/transitions",
            json={"transition": {"id": transition_id}},
        )
        resp.raise_for_status()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
