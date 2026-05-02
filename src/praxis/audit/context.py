"""Audit context management via ContextVar.

Use :func:`set_audit_context` to set the active profile and engagement
for audit event emission.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuditContext:
    """Current audit context — profile and engagement scope."""

    profile: str = "default"
    engagement: str | None = None
    engagement_path: Path | None = None


_EMPTY_CONTEXT = AuditContext()
_audit_context: ContextVar[AuditContext] = ContextVar("audit_context")


def get_audit_context() -> AuditContext:
    """Return the current audit context."""
    return _audit_context.get(_EMPTY_CONTEXT)


@contextmanager
def set_audit_context(
    profile: str = "default",
    engagement: str | None = None,
    engagement_path: Path | None = None,
) -> Generator[AuditContext, None, None]:
    """Set the audit context for the current scope.

    Args:
        profile: Active profile name.
        engagement: Engagement name.
        engagement_path: Path to the engagement root directory.

    Yields:
        The new :class:`AuditContext`.
    """
    ctx = AuditContext(
        profile=profile,
        engagement=engagement,
        engagement_path=engagement_path,
    )
    token = _audit_context.set(ctx)
    try:
        yield ctx
    finally:
        _audit_context.reset(token)
