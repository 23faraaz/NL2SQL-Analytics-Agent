"""
Chooses which LLMProvider implementation backs the pipeline.

Selection is controlled by the LLM_PROVIDER environment variable: "gemini"
or "groq". An unset LLM_PROVIDER defaults to "gemini" to preserve current
behaviour, and any other value fails fast with a clear LLMError rather
than silently falling back to Gemini or picking an arbitrary provider.
There is no automatic fallback between providers -- switching requires
explicitly changing LLM_PROVIDER.

This is the one place that knows about concrete provider modules --
app/llm/pipeline.py only ever sees the LLMProvider interface returned by
get_provider() below, never a provider module directly.
"""

import os

from . import gemini_provider, groq_provider
from .base import LLMError, LLMProvider

DEFAULT_PROVIDER = "gemini"

_PROVIDERS = {
    "gemini": gemini_provider,
    "groq": groq_provider,
}


def _resolve_provider_name() -> str:
    return (os.environ.get("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()


def _resolve_provider_module():
    provider_name = _resolve_provider_name()
    module = _PROVIDERS.get(provider_name)

    if module is None:
        raise LLMError(
            f"Unsupported LLM_PROVIDER '{provider_name}'. "
            f"Supported providers: {', '.join(sorted(_PROVIDERS))}."
        )

    return module


def validate_config() -> None:
    """Fail-fast startup check, delegated to whichever provider is configured."""

    _resolve_provider_module().validate_config()


def get_provider() -> LLMProvider:
    """Return a ready-to-use LLMProvider instance for the configured provider."""

    return _resolve_provider_module().get_provider()
