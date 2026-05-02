"""Praxis audit subsystem — public API.

Structured, immutable audit logging to JSONL files and SQLite.
"""

from .context import AuditContext, get_audit_context, set_audit_context
from .models import AuditEvent
from .reader import query, tail
from .writer import emit

__all__ = [
    "AuditContext",
    "AuditEvent",
    "emit",
    "get_audit_context",
    "query",
    "set_audit_context",
    "tail",
]
