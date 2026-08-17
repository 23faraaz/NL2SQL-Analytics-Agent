"""
Provider-independent LLM abstraction.

No provider SDK, provider-specific exception type, or provider-specific
configuration belongs here -- only the interface app/llm/pipeline.py
codes against and the single exception type the whole LLM layer raises,
regardless of which provider is configured.
"""

from abc import ABC, abstractmethod
from typing import Any


class LLMError(Exception):
    """Single exception type exposed by the LLM layer, regardless of provider."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        """
        Return the raw text response for a prompt.

        Structured JSON output is requested when json_schema is supplied;
        the returned string is the provider's raw text response either
        way -- parsing is the caller's responsibility.
        """
