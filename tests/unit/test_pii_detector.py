"""Unit tests for praxis.safety.pii detectors (D-043)."""

from __future__ import annotations

import pytest

from praxis.safety.pii import PIIKind, detect_pii, pii_guard_enabled


class TestSSNDetection:
    def test_detects_canonical_ssn(self) -> None:
        assert PIIKind.SSN in detect_pii("The SSN is 123-45-6789.")

    def test_ignores_text_without_ssn(self) -> None:
        assert detect_pii("Just a normal sentence about loans.") == []

    def test_ignores_phone_number_format(self) -> None:
        # Standard US phone format is 3-3-4, not 3-2-4 — should not trigger SSN.
        assert PIIKind.SSN not in detect_pii("Call 555-555-1234 today.")


class TestCreditCardDetection:
    def test_detects_valid_visa_with_spaces(self) -> None:
        # 4111 1111 1111 1111 is a well-known Luhn-valid Visa test number.
        assert PIIKind.CREDIT_CARD in detect_pii("Card: 4111 1111 1111 1111")

    def test_detects_valid_visa_with_hyphens(self) -> None:
        assert PIIKind.CREDIT_CARD in detect_pii("Card: 4111-1111-1111-1111")

    def test_ignores_luhn_invalid_16_digit_string(self) -> None:
        # 1234 5678 9012 3456 fails Luhn — should NOT trigger CC.
        assert PIIKind.CREDIT_CARD not in detect_pii("Nonsense: 1234 5678 9012 3456")

    def test_ignores_random_short_digit_runs(self) -> None:
        # 12 digits — below the 13-digit minimum even before Luhn.
        assert PIIKind.CREDIT_CARD not in detect_pii("Order 123456789012 shipped.")


class TestGuardEnabled:
    def test_enabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PRAXIS_PII_GUARD", raising=False)
        assert pii_guard_enabled() is True

    def test_disabled_when_env_set_to_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "off")
        assert pii_guard_enabled() is False

    def test_disabled_is_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "OFF")
        assert pii_guard_enabled() is False

    def test_other_values_keep_guard_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAXIS_PII_GUARD", "on")
        assert pii_guard_enabled() is True


class TestMixedAndOrdering:
    def test_both_kinds_detected_in_one_input(self) -> None:
        text = "SSN 123-45-6789 and card 4111-1111-1111-1111"
        result = detect_pii(text)
        assert PIIKind.SSN in result
        assert PIIKind.CREDIT_CARD in result

    def test_result_is_deduplicated(self) -> None:
        # Two SSNs but only one kind reported.
        text = "SSN1 123-45-6789, SSN2 987-65-4321"
        result = detect_pii(text)
        assert result.count(PIIKind.SSN) == 1
