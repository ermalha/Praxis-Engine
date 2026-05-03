"""Praxis exception hierarchy.

Every subsystem has a dedicated exception class that inherits from PraxisError.
All errors carry a ``details`` dict for structured context.
"""


class PraxisError(Exception):
    """Base for all Praxis errors."""

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.details: dict[str, object] = dict(details)


class ConfigError(PraxisError):
    """Configuration or profile error."""


class StorageError(PraxisError):
    """SQLite or file-system storage error."""


class TransportError(PraxisError):
    """LLM transport / provider error."""


class ToolError(PraxisError):
    """Tool registry or execution error."""


class SkillError(PraxisError):
    """Skill loading or execution error."""


class EngagementError(PraxisError):
    """Engagement model error."""


class WorkqueueError(PraxisError):
    """Work-queue error."""


class SufficiencyError(PraxisError):
    """Sufficiency gate error."""


class OrchestratorError(PraxisError):
    """Orchestrator / wake-cycle error."""


class AuditError(PraxisError):
    """Audit logging error."""
