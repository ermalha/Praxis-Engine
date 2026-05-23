"""Provider-error translation helper (D-051).

The OpenAI + Anthropic Python SDKs share a Stainless-generated exception
hierarchy: same class names, same ``status_code`` attribute. This module
duck-types on class name (no SDK import at module load) and maps each
known kind to a user-friendly :class:`TransportError` with a structured
``details["kind"]`` so callers can branch programmatically without
string-matching the message.

Unknown / non-SDK exceptions fall through to the legacy generic message
so behaviour is strictly additive — existing callers' assertions on
``provider`` + the substring still pass.
"""

from __future__ import annotations

from praxis.errors import TransportError

# Stainless-generated exception class names that both SDKs share.
_HTTP_KIND_BY_NAME: dict[str, str] = {
    "AuthenticationError": "auth",
    "PermissionDeniedError": "permission",
    "RateLimitError": "rate_limit",
    "NotFoundError": "not_found",
    "BadRequestError": "bad_request",
    "InternalServerError": "server_error",
}

_NETWORK_KIND_BY_NAME: dict[str, str] = {
    "APIConnectionError": "connection",
    "APITimeoutError": "timeout",
    # httpx-direct names — appear when an SDK lets the underlying error escape.
    "ConnectError": "connection",
    "TimeoutException": "timeout",
}

_KIND_TEMPLATES: dict[str, str] = {
    "auth": (
        "Authentication failed for {provider}. Check that env var "
        "${api_key_env} is set and the key is valid."
    ),
    "permission": (
        "Permission denied by {provider}. Your API key lacks access to model '{model}'."
    ),
    "rate_limit": (
        "Rate limit exceeded for {provider}. Wait and retry, or upgrade your account tier."
    ),
    "not_found": "Model '{model}' not found for provider {provider}.",
    "bad_request": "Request rejected by {provider}: {detail}.",
    "server_error": ("{provider_title} API error (server-side): {detail}. Retry later."),
    "connection": ("Network error reaching {provider}: {detail}. Check your connection."),
    "timeout": "Request timed out reaching {provider}.",
}


def _classify(exc: Exception) -> str:
    """Return a stable kind string for a known SDK exception, or 'unknown'."""
    module = type(exc).__module__
    if not (
        module.startswith("openai") or module.startswith("anthropic") or module.startswith("httpx")
    ):
        return "unknown"
    name = type(exc).__name__
    if name in _HTTP_KIND_BY_NAME:
        return _HTTP_KIND_BY_NAME[name]
    if name in _NETWORK_KIND_BY_NAME:
        return _NETWORK_KIND_BY_NAME[name]
    return "unknown"


def translate_provider_exception(
    exc: Exception,
    *,
    provider: str,
    model: str | None = None,
    api_key_env: str | None = None,
    fallback_message: str = "{provider_title} API call failed: {detail}",
) -> TransportError:
    """Convert an SDK exception into a user-friendly :class:`TransportError`.

    Args:
        exc: The exception caught from the SDK / HTTP layer.
        provider: Provider name (``"openai"`` / ``"anthropic"`` / ``"openrouter"``).
        model: Model identifier to interpolate into messages.
        api_key_env: Env-var name carrying the API key; used in the auth
            error message so the user knows exactly which variable to set.
        fallback_message: Template used when the exception is unrecognised.
            Receives ``provider``, ``provider_title``, ``detail`` keys.

    Returns:
        A :class:`TransportError` carrying ``provider`` and ``kind`` in
        ``details``, with a message tailored to the error class.
    """
    kind = _classify(exc)
    detail = str(exc) or type(exc).__name__
    provider_title = provider[:1].upper() + provider[1:]

    if kind == "unknown":
        msg = fallback_message.format(
            provider=provider,
            provider_title=provider_title,
            detail=detail,
        )
        return TransportError(msg, provider=provider, kind=kind)

    template = _KIND_TEMPLATES[kind]
    msg = template.format(
        provider=provider,
        provider_title=provider_title,
        model=model or "<unknown>",
        api_key_env=api_key_env or "API_KEY",
        detail=detail,
    )
    return TransportError(msg, provider=provider, kind=kind)
