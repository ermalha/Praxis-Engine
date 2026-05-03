"""Praxis integrations subsystem.

Optional connectors for external services.  Each integration is lazy-loaded
and degrades gracefully when its dependencies are not installed or the
integration is disabled in the engagement config.
"""

from praxis.integrations.base import Integration
from praxis.integrations.models import HealthResult, HealthStatus
from praxis.integrations.registry import (
    get_integration,
    list_registered,
    register_integration,
)

__all__ = [
    "HealthResult",
    "HealthStatus",
    "Integration",
    "get_integration",
    "list_registered",
    "register_integration",
]
