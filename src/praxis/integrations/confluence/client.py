"""Confluence REST API client."""

from __future__ import annotations

import os
from typing import Any

import httpx

from praxis.errors import IntegrationError


class ConfluenceClient:
    """Thin wrapper around the Confluence REST API."""

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
            base_url=f"{self._base}/wiki/rest/api",
            auth=(email, token),
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    @classmethod
    def from_settings(cls, settings: dict[str, str]) -> ConfluenceClient:
        """Create a client from integration settings dict."""
        base_url = settings.get("base_url", "")
        if not base_url:
            raise IntegrationError("Confluence base_url not configured", kind="confluence")
        email_env = settings.get("email_env", "CONFLUENCE_EMAIL")
        token_env = settings.get("token_env", "CONFLUENCE_TOKEN")
        email = os.environ.get(email_env, "")
        token = os.environ.get(token_env, "")
        if not email or not token:
            raise IntegrationError(
                f"Confluence credentials missing: set {email_env} and {token_env}",
                kind="confluence",
            )
        return cls(base_url=base_url, email=email, token=token)

    def search(self, cql: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search content using CQL."""
        resp = self._client.get(
            "/content/search",
            params={"cql": cql, "limit": limit},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def get_page(
        self,
        space: str | None = None,
        title: str | None = None,
        page_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a page by ID or by space + title."""
        if page_id:
            resp = self._client.get(
                f"/content/{page_id}",
                params={"expand": "body.storage,version"},
            )
            resp.raise_for_status()
            return resp.json()

        if not space or not title:
            raise IntegrationError(
                "Either page_id or both space and title are required",
                kind="confluence",
            )
        resp = self._client.get(
            "/content",
            params={
                "spaceKey": space,
                "title": title,
                "expand": "body.storage,version",
            },
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            raise IntegrationError(
                f"Page not found: {space}/{title}",
                kind="confluence",
            )
        return results[0]

    def create_page(
        self,
        space: str,
        title: str,
        body: str,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new Confluence page."""
        payload: dict[str, Any] = {
            "type": "page",
            "title": title,
            "space": {"key": space},
            "body": {"storage": {"value": body, "representation": "storage"}},
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]
        resp = self._client.post("/content", json=payload)
        resp.raise_for_status()
        return resp.json()

    def update_page(self, page_id: str, body: str, title: str | None = None) -> dict[str, Any]:
        """Update an existing page's body."""
        current = self.get_page(page_id=page_id)
        version = current.get("version", {}).get("number", 1) + 1
        page_title = title or current.get("title", "Untitled")
        payload = {
            "version": {"number": version},
            "title": page_title,
            "type": "page",
            "body": {"storage": {"value": body, "representation": "storage"}},
        }
        resp = self._client.put(f"/content/{page_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
