"""
Public LLM-layer API used by app/main.py.

main.py should not need to know which provider is configured -- it only
calls the functions re-exported here. Provider selection happens in
factory.py; the concrete provider (currently only Gemini) is isolated in
gemini_provider.py and is never imported directly by this module or by
pipeline.py.

Dependency direction: main.py -> this package -> base.LLMProvider
interface -> factory.py (chooses) -> gemini_provider.py -> google.genai.
"""

from .base import LLMError
from .factory import validate_config
from .pipeline import (
    explain_results,
    regenerate_sql,
    suggest_followups,
    understand_and_generate_sql,
)

__all__ = [
    "LLMError",
    "validate_config",
    "understand_and_generate_sql",
    "regenerate_sql",
    "explain_results",
    "suggest_followups",
]
