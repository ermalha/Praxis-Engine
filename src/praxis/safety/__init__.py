"""Praxis safety subsystem — PII detection and other input/output guards.

Exposes the PII guard used by ``praxis ask`` and ``praxis chat`` to
detect SSNs + Luhn-valid credit-card numbers in LLM-bound input. The
guard supports four policy modes (off / warn / block / redact) selected
via ``PRAXIS_PII_GUARD`` — see :func:`apply_pii_policy`.
"""

from .pii import (
    PIIBlockedError,
    PIIGuardMode,
    PIIKind,
    apply_pii_policy,
    detect_pii,
    pii_guard_enabled,
    resolve_pii_guard_mode,
    warn_on_pii,
)

__all__ = [
    "PIIBlockedError",
    "PIIGuardMode",
    "PIIKind",
    "apply_pii_policy",
    "detect_pii",
    "pii_guard_enabled",
    "resolve_pii_guard_mode",
    "warn_on_pii",
]
