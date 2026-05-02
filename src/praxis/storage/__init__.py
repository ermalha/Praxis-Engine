"""Praxis storage subsystem — public API.

Provides SQLite-backed repositories and file-based storage helpers.
"""

from .db import close_connection, get_connection, init_db, run_migrations
from .files import (
    read_markdown_with_frontmatter,
    read_yaml_typed,
    write_markdown_with_frontmatter,
    write_yaml_typed,
)
from .models import (
    FTSResult,
    Message,
    MessageRole,
    Session,
    WorkItem,
    WorkItemPriority,
    WorkItemStatus,
)
from .repos import AuditRepo, MessageRepo, SessionRepo, WorkItemRepo

__all__ = [
    # Connection
    "close_connection",
    "get_connection",
    "init_db",
    "run_migrations",
    # File helpers
    "read_markdown_with_frontmatter",
    "read_yaml_typed",
    "write_markdown_with_frontmatter",
    "write_yaml_typed",
    # Models
    "FTSResult",
    "Message",
    "MessageRole",
    "Session",
    "WorkItem",
    "WorkItemPriority",
    "WorkItemStatus",
    # Repos
    "AuditRepo",
    "MessageRepo",
    "SessionRepo",
    "WorkItemRepo",
]
