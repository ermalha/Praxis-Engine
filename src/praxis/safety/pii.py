"""PII detection for ``ask`` / ``chat`` user input (D-043).

Warn-only — never blocks or redacts. The goal is to make a user pause
before pasting an SSN or credit card into a prompt that will be sent to
an external LLM provider. Set ``PRAXIS_PII_GUARD=off`` to silence the
warning entirely.

Detectors:
- SSN: ``\\b\\d{3}-\\d{2}-\\d{4}\\b``
- Credit card: 13–19-digit candidates (allowing space/hyphen separators)
  verified with the Luhn checksum, which keeps false positives low.

Routing numbers and date-of-birth heuristics are deliberately not
included — they produce too many false positives for a warn-only guard.
"""

from __future__ import annotations

import os
import re
from enum import StrEnum


class PIIKind(StrEnum):
    """Categories of PII the guard recognises."""

    SSN = "ssn"
    CREDIT_CARD = "credit_card"


_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Match runs of 13-19 digits, optionally separated by spaces or hyphens
# (e.g. "4111 1111 1111 1111" or "4111-1111-1111-1111"). The
# trailing/leading lookaround keeps us from gluing into longer numeric
# blobs like "12341234123412345678" (20 digits → not a card).
_CC_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _luhn_check(digits: str) -> bool:
    """Standard Luhn checksum. Returns True if ``digits`` (all numeric) passes."""
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def detect_pii(text: str) -> list[PIIKind]:
    """Return a sorted list of PIIKind matches in *text* (deduplicated).

    Empty list when nothing matches. Safe to call on arbitrary user input.
    """
    found: set[PIIKind] = set()

    if _SSN_RE.search(text):
        found.add(PIIKind.SSN)

    for m in _CC_CANDIDATE_RE.finditer(text):
        digits = re.sub(r"[ -]", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_check(digits):
            found.add(PIIKind.CREDIT_CARD)
            break

    return sorted(found)


def pii_guard_enabled() -> bool:
    """Return False when ``PRAXIS_PII_GUARD`` is set to ``off`` (any case)."""
    return os.environ.get("PRAXIS_PII_GUARD", "").strip().lower() != "off"


def warn_on_pii(text: str) -> list[PIIKind]:
    """If PII is detected and the guard is enabled, print a stderr warning.

    Returns the list of detected PIIKinds (empty when nothing matched or
    the guard is disabled). Never blocks: callers are expected to send
    *text* to the LLM regardless.
    """
    if not pii_guard_enabled():
        return []
    matches = detect_pii(text)
    if not matches:
        return matches

    # Lazy-import Rich Console to avoid importing it during pure-detection use.
    from rich.console import Console

    kinds = ", ".join(k.value for k in matches)
    err = Console(stderr=True)
    err.print(
        f"[yellow]WARNING:[/yellow] Detected what looks like PII ({kinds}) in your "
        "input. Praxis is sending this to the LLM provider. If this is real "
        "sensitive data, redact and retry. (Set PRAXIS_PII_GUARD=off to silence.)"
    )
    return matches
