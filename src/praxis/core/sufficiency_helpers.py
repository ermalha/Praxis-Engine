"""Template loader for sufficiency gate information needs."""

from __future__ import annotations

from pathlib import Path

import yaml

_TEMPLATES_DIR = Path(__file__).parent / "sufficiency_templates"

# Cache templates in memory after first load
_template_cache: dict[str, list[dict[str, object]]] = {}


def load_template(artifact_kind: str) -> list[dict[str, object]]:
    """Load pre-populated info needs for a known artifact kind.

    Returns a list of dicts with ``need`` and ``blocker`` keys.
    Returns an empty list for unknown artifact kinds (the LLM will
    enumerate needs from scratch).
    """
    if artifact_kind in _template_cache:
        return _template_cache[artifact_kind]

    path = _TEMPLATES_DIR / f"{artifact_kind}.yaml"
    if not path.is_file():
        return []

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    needs: list[dict[str, object]] = data.get("information_needs", [])
    _template_cache[artifact_kind] = needs
    return needs


def list_template_kinds() -> list[str]:
    """Return the artifact kinds with available templates."""
    return sorted(p.stem for p in _TEMPLATES_DIR.glob("*.yaml"))


def clear_cache() -> None:
    """Clear the template cache (for testing)."""
    _template_cache.clear()
