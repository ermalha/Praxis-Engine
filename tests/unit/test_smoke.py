"""Smoke tests — verify the package is importable and basics work."""

from praxis import PraxisError, __version__


def test_version_is_string() -> None:
    assert isinstance(__version__, str)


def test_praxis_error_carries_details() -> None:
    err = PraxisError("oops", code=42)
    assert err.details == {"code": 42}
