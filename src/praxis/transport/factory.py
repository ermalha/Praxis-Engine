"""Transport factory — select the right adapter based on ``ModelConfig``."""

from __future__ import annotations

from praxis.config.models import ModelConfig, Provider
from praxis.errors import TransportError
from praxis.transport.base import Transport


def make_transport(model_config: ModelConfig) -> Transport:
    """Create a :class:`Transport` from a :class:`ModelConfig`.

    Adapters are imported lazily so optional dependencies (``anthropic``,
    ``openai``) are only required when actually used.
    """
    provider = model_config.provider

    if provider == Provider.ANTHROPIC:
        from praxis.transport.anthropic_adapter import AnthropicTransport

        return AnthropicTransport(
            api_key_env=model_config.api_key_env,
            model=model_config.model,
            timeout_s=model_config.timeout_s,
        )

    if provider == Provider.OPENAI:
        from praxis.transport.openai_adapter import OpenAITransport

        return OpenAITransport(
            api_key_env=model_config.api_key_env,
            model=model_config.model,
            base_url=str(model_config.base_url) if model_config.base_url else None,
            timeout_s=model_config.timeout_s,
            extra_headers=model_config.extra_headers or None,
        )

    if provider == Provider.OPENROUTER:
        from praxis.transport.openrouter_adapter import OpenRouterTransport

        return OpenRouterTransport(
            api_key_env=model_config.api_key_env,
            model=model_config.model,
            timeout_s=model_config.timeout_s,
            extra_headers=model_config.extra_headers or None,
        )

    if provider == Provider.OPENAI_COMPAT:
        from praxis.transport.compat_adapter import CompatTransport

        if not model_config.base_url:
            raise TransportError(
                "OpenAI-compatible provider requires a base_url",
                provider="openai_compat",
            )
        return CompatTransport(
            api_key_env=model_config.api_key_env,
            model=model_config.model,
            base_url=str(model_config.base_url),
            timeout_s=model_config.timeout_s,
            extra_headers=model_config.extra_headers or None,
        )

    raise TransportError(f"Unknown provider: {provider}", provider=str(provider))
