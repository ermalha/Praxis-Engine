"""OpenRouter transport adapter.

Extends the OpenAI adapter with the required ``HTTP-Referer`` and
``X-Title`` headers, pointed at the OpenRouter base URL.
"""

from __future__ import annotations

from praxis.transport.openai_adapter import OpenAITransport

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterTransport(OpenAITransport):
    """Adapter for OpenRouter (OpenAI-compatible with extra headers)."""

    name = "openrouter"

    def __init__(
        self,
        api_key_env: str,
        model: str,
        *,
        timeout_s: int = 120,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        headers = {
            "HTTP-Referer": "https://github.com/praxis-framework/praxis",
            "X-Title": "Praxis BA Framework",
        }
        if extra_headers:
            headers.update(extra_headers)

        super().__init__(
            api_key_env=api_key_env,
            model=model,
            base_url=_OPENROUTER_BASE_URL,
            timeout_s=timeout_s,
            extra_headers=headers,
        )

    def supports_caching(self) -> bool:
        return False
