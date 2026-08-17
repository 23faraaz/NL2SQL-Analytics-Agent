"""
Tests for app/llm/factory.py -- provider selection via LLM_PROVIDER.

No network calls: get_provider() only constructs a provider instance,
it does not validate credentials or make a request.
"""

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from llm import factory, gemini_provider, groq_provider  # noqa: E402


def test_unset_llm_provider_defaults_to_gemini(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    provider = factory.get_provider()

    assert isinstance(provider, gemini_provider.GeminiProvider)


def test_explicit_gemini_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")

    provider = factory.get_provider()

    assert isinstance(provider, gemini_provider.GeminiProvider)


def test_explicit_groq_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")

    provider = factory.get_provider()

    assert isinstance(provider, groq_provider.GroqProvider)


def test_provider_name_is_case_and_whitespace_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "  GROQ  ")

    provider = factory.get_provider()

    assert isinstance(provider, groq_provider.GroqProvider)


def test_unknown_provider_raises_on_get_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown")

    with pytest.raises(factory.LLMError, match="Unsupported LLM_PROVIDER"):
        factory.get_provider()


def test_unknown_provider_raises_on_validate_config(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown")

    with pytest.raises(factory.LLMError, match="Unsupported LLM_PROVIDER"):
        factory.validate_config()


def test_unknown_provider_does_not_silently_fall_back_to_gemini(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")

    with pytest.raises(factory.LLMError) as exc_info:
        factory.get_provider()

    assert "gemini" in str(exc_info.value)
    assert "groq" in str(exc_info.value)


def test_validate_config_delegates_to_the_selected_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(groq_provider, "MODEL", "openai/gpt-oss-20b")

    factory.validate_config()  # must not raise -- delegated to groq_provider
