"""PII detection + policy enforcement for LLM-bound input.

D-043 introduced the detector (warn-only). D-065 adds policy modes so
audit-conscious deployments can opt into stronger handling:

- ``off``    — no detection, no warning, no block.
- ``warn``   — (default) detect, warn on stderr, send anyway.
- ``block``  — detect; if any PII matches, refuse to send and exit
                non-zero. The caller can suggest ``--redact`` or
                ``PRAXIS_PII_GUARD=redact``.
- ``redact`` — detect; replace each match with a type-tagged token
                (``[SSN]`` / ``[CC]``) before sending; print a stderr
                summary of what was redacted.

Mode resolution today is env-var only (``PRAXIS_PII_GUARD``).
Profile-level overrides + a per-command ``--pii-guard`` flag are
queued as follow-ups when there's user demand.

Detectors:
- SSN: ``\\b\\d{3}-\\d{2}-\\d{4}\\b``
- Credit card: 13–19-digit candidates (allowing space/hyphen separators)
  verified with the Luhn checksum, which keeps false positives low.

Routing numbers and date-of-birth heuristics are deliberately not
included — they produce too many false positives at any guard level.
"""

from __future__ import annotations

import os
import re
from enum import StrEnum


class PIIKind(StrEnum):
    """Categories of PII the guard recognises."""

    SSN = "ssn"
    CREDIT_CARD = "credit_card"


class PIIGuardMode(StrEnum):
    """Policy levels for PII handling on LLM-bound input."""

    OFF = "off"
    WARN = "warn"
    BLOCK = "block"
    REDACT = "redact"


# Token replacements used in ``redact`` mode.
_REDACT_TOKENS: dict[PIIKind, str] = {
    PIIKind.SSN: "[SSN]",
    PIIKind.CREDIT_CARD: "[CC]",
}


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


def resolve_pii_guard_mode() -> PIIGuardMode:
    """Resolve the active PII-guard mode from ``$PRAXIS_PII_GUARD``.

    Unknown values fall back to ``warn`` (the default) — better to keep
    sending with a warning than silently disable on a typo.
    """
    raw = os.environ.get("PRAXIS_PII_GUARD", "").strip().lower()
    if raw == "":
        return PIIGuardMode.WARN
    try:
        return PIIGuardMode(raw)
    except ValueError:
        return PIIGuardMode.WARN


def pii_guard_enabled() -> bool:
    """Return False when the guard is fully disabled (mode == ``off``).

    Kept for backwards-compatibility with the D-043 surface; new callers
    should use :func:`resolve_pii_guard_mode` directly.
    """
    return resolve_pii_guard_mode() is not PIIGuardMode.OFF


def _redact(text: str, kinds: list[PIIKind]) -> str:
    """Replace each detected PII match with a type-tagged token.

    Only redacts the kinds passed in (so callers can choose to redact a
    subset, e.g. once per kind for testability).
    """
    redacted = text
    if PIIKind.SSN in kinds:
        redacted = _SSN_RE.sub(_REDACT_TOKENS[PIIKind.SSN], redacted)
    if PIIKind.CREDIT_CARD in kinds:
        # Re-scan to replace each Luhn-valid candidate. Non-Luhn-valid
        # digit runs are left alone so we don't redact e.g. phone numbers.
        def _replace_if_luhn(m: re.Match[str]) -> str:
            digits = re.sub(r"[ -]", "", m.group())
            if 13 <= len(digits) <= 19 and _luhn_check(digits):
                return _REDACT_TOKENS[PIIKind.CREDIT_CARD]
            return m.group()

        redacted = _CC_CANDIDATE_RE.sub(_replace_if_luhn, redacted)
    return redacted


class PIIBlockedError(Exception):
    """Raised by :func:`apply_pii_policy` when ``mode == block`` and PII is found.

    Carries ``kinds`` (the detected PIIKinds) so CLI callers can render a
    helpful message naming what triggered the block.
    """

    def __init__(self, kinds: list[PIIKind]) -> None:
        self.kinds = kinds
        names = ", ".join(k.value for k in kinds)
        super().__init__(
            f"Input contains PII ({names}); PRAXIS_PII_GUARD=block refused to send. "
            "Set PRAXIS_PII_GUARD=redact to mask, =warn to send anyway, or =off to disable."
        )


def apply_pii_policy(text: str) -> tuple[str, list[PIIKind]]:
    """Apply the active PII-guard policy to *text* before LLM dispatch.

    Returns ``(text_to_send, detected_kinds)``. In ``redact`` mode the
    returned text has been mutated; in ``warn`` mode the returned text
    equals the input and a stderr warning has been printed; in ``off``
    mode no detection runs. ``block`` mode raises :class:`PIIBlockedError`
    when PII is found — the caller is expected to surface the message
    and exit non-zero.
    """
    mode = resolve_pii_guard_mode()
    if mode is PIIGuardMode.OFF:
        return text, []

    kinds = detect_pii(text)
    if not kinds:
        return text, []

    # Lazy-import Rich Console — keeps pure-detection paths import-light.
    from rich.console import Console

    err = Console(stderr=True)
    names = ", ".join(k.value for k in kinds)

    if mode is PIIGuardMode.WARN:
        err.print(
            f"[yellow]WARNING:[/yellow] Detected what looks like PII ({names}) in your "
            "input. Praxis is sending this to the LLM provider. If this is real "
            "sensitive data, redact and retry. (Set PRAXIS_PII_GUARD=redact to mask, "
            "=block to refuse, =off to silence.)"
        )
        return text, kinds

    if mode is PIIGuardMode.REDACT:
        masked = _redact(text, kinds)
        err.print(
            f"[yellow]REDACTED:[/yellow] PRAXIS_PII_GUARD=redact masked {names} "
            "before sending to the LLM provider."
        )
        return masked, kinds

    # mode is PIIGuardMode.BLOCK
    raise PIIBlockedError(kinds)


def warn_on_pii(text: str) -> list[PIIKind]:
    """Back-compat shim — runs the policy and swallows any block error.

    Used by callers that haven't migrated to :func:`apply_pii_policy`'s
    block-aware signature yet. Returns the detected kinds (empty when
    none found or when the guard is off).

    New callers should use :func:`apply_pii_policy` directly so
    ``block``/``redact`` modes work.
    """
    try:
        _, kinds = apply_pii_policy(text)
    except PIIBlockedError as exc:
        return exc.kinds
    return kinds
