"""Praxis safety subsystem — PII detection and other input/output guards.

Currently exposes the PII guard used by ``praxis ask`` and ``praxis chat``
to warn (not block) when user input contains an SSN or Luhn-valid
credit-card number.
"""

from .pii import PIIKind, detect_pii, pii_guard_enabled, warn_on_pii

__all__ = [
    "PIIKind",
    "detect_pii",
    "pii_guard_enabled",
    "warn_on_pii",
]
