"""Integration registry — discover and instantiate integrations by kind."""

from __future__ import annotations

from praxis.config.models import IntegrationConfig
from praxis.errors import IntegrationError
from praxis.integrations.base import Integration

_REGISTRY: dict[str, type[Integration]] = {}


def register_integration(cls: type[Integration]) -> type[Integration]:
    """Class decorator that registers an integration by its ``kind``."""
    kind = cls.kind
    if kind in _REGISTRY:
        raise IntegrationError(
            f"Duplicate integration kind: {kind!r}",
            kind=kind,
        )
    _REGISTRY[kind] = cls
    return cls


def get_integration(kind: str, config: IntegrationConfig) -> Integration:
    """Instantiate a registered integration.

    Raises :class:`IntegrationError` if *kind* is not registered.
    """
    cls = _REGISTRY.get(kind)
    if cls is None:
        raise IntegrationError(
            f"Unknown integration kind: {kind!r}",
            kind=kind,
            available=list(_REGISTRY),
        )
    return cls(config)


def list_registered() -> list[str]:
    """Return the kinds of all registered integrations."""
    return sorted(_REGISTRY)


def _reset_registry() -> None:
    """Clear for testing."""
    _REGISTRY.clear()
