"""ID generation helpers for engagement model entities."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len]


def _short_uuid() -> str:
    """Generate a short (8-char) UUID."""
    return uuid.uuid4().hex[:8]


def stakeholder_id(name: str) -> str:
    """Generate a stakeholder ID from name."""
    return f"{_slugify(name)}-{_short_uuid()}"


def decision_id(title: str) -> str:
    """Generate an ADR-style decision ID."""
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"ADR-{date_str}-{_slugify(title, max_len=30)}"


def short_id() -> str:
    """Generate a short UUID for questions, risks, etc."""
    return _short_uuid()
