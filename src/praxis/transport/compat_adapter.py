"""Generic OpenAI-compatible transport adapter.

Works with Ollama, vLLM, LM Studio, Groq, Together, and any server
exposing the OpenAI Chat Completions API.
"""

from __future__ import annotations

from praxis.transport.openai_adapter import OpenAITransport


class CompatTransport(OpenAITransport):
    """Adapter for generic OpenAI-compatible servers."""

    name = "openai_compat"

    def __init__(
        self,
        api_key_env: str,
        model: str,
        *,
        base_url: str,
        timeout_s: int = 120,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            api_key_env=api_key_env,
            model=model,
            base_url=base_url,
            timeout_s=timeout_s,
            extra_headers=extra_headers,
        )

    def supports_tools(self) -> bool:
        # Many local servers don't support tools; conservative default
        return False

    def supports_caching(self) -> bool:
        return False
