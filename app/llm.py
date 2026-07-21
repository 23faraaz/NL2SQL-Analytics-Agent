"""
LLM layer - Gemini variant. Drop-in alternative to llm.py.

Every function here matches llm.py's signature exactly (same name, same
args, same return type) so main.py doesn't need to change at all beyond
the import line:

    from app import llm            # Claude version
    from app import llm_gemini as llm   # Gemini version

WHY GEMINI'S response_schema IS USED INSTEAD OF PROMPT-ASKING FOR JSON:
Unlike the Claude version (which asks nicely for JSON in the prompt and
defensively strips markdown fences from the response), Gemini's API has a
native structured-output mode: pass response_mime_type="application/json"
plus a response_schema, and the API guarantees schema-conformant JSON back
- no fence-stripping, no "please don't wrap this in markdown" prompt
engineering needed. Worth pointing out in an interview as a genuine
capability difference between providers, not just a syntax difference.
"""

import json
import logging
import os

from google import genai
from google.genai import types

import prompts

logger = logging.getLogger(__name__)

MODEL = "gemini-3.5-flash"
MAX_TOKENS = 2048


class LLMError(Exception):
    """Same contract as llm.py's LLMError - callers catch this one type
    regardless of which provider module is imported as `llm`."""
    pass


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMError("GEMINI_API_KEY environment variable is not set.")
    return genai.Client(api_key=api_key)


def _call_gemini(prompt: str, json_schema: dict | None = None) -> str:
    """
    Single shared call path, same role as _call_claude() in llm.py.
    If json_schema is provided, uses Gemini's native structured-output
    mode instead of relying on prompt instructions.
    """
    client = _get_client()
    config = types.GenerateContentConfig(max_output_tokens=MAX_TOKENS)

    if json_schema is not None:
        config = types.GenerateContentConfig(
            max_output_tokens=MAX_TOKENS,
            response_mime_type="application/json",
            response_schema=json_schema,
        )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=config,
        )
        if not response.text:
            raise LLMError("Gemini returned an empty response.")
        return response.text.strip()
    except Exception as e:
        # The google-genai SDK raises genai.errors.APIError for API-level
        # failures, but network/timeout errors can surface as other
        # exception types - catching broadly here and wrapping in LLMError
        # keeps the same "one exception type" contract callers rely on.
        logger.error("Gemini API call failed: %s", e) 
        raise LLMError(f"Gemini API call failed: {e}") from e


def understand_question(question: str, schema: str) -> dict:
    """Step 1: extract intent, entities, and time filters from the question."""
    prompt = prompts.QUESTION_UNDERSTANDING_PROMPT.format(schema=schema, question=question)

    json_schema = {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "entities": {"type": "array", "items": {"type": "string"}},
            "time_filter": {"type": "string", "nullable": True},
            "aggregation": {"type": "string", "nullable": True},
        },
        "required": ["intent", "entities"],
    }

    response_text = _call_gemini(prompt, json_schema=json_schema)
    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON from question understanding: %s", e)
        raise LLMError(f"Could not parse Gemini's response: {response_text[:200]}") from e

    logger.info("Question understood: intent=%s", result.get("intent"))
    return result


def generate_sql(question: str, schema: str, understanding: dict) -> str:
    """Step 2: generate a SELECT query using the discovered schema."""
    prompt = prompts.SQL_GENERATION_PROMPT.format(
        schema=schema,
        question=question,
        understanding=json.dumps(understanding, indent=2),
    )
    # No JSON schema here - this step's output is raw SQL text, not
    # structured data, so we fall back to the same defensive markdown-fence
    # stripping the Claude version uses.
    sql = _call_gemini(prompt)

    if sql.startswith("```"):
        sql = sql.split("```")[1]
        sql = sql.removeprefix("sql").strip()

    logger.info("SQL generated (%d chars)", len(sql))
    return sql.strip()


def explain_results(question: str, sql: str, columns: list[str], rows: list[tuple]) -> str:
    """Step 3: turn raw query results into a plain-English explanation."""
    preview_rows = rows[:20]
    results_text = "\n".join(
        [", ".join(columns)] + [", ".join(str(v) for v in row) for row in preview_rows]
    )

    prompt = prompts.RESULT_EXPLANATION_PROMPT.format(
        question=question,
        sql=sql,
        row_count=len(rows),
        results=results_text,
    )
    explanation = _call_gemini(prompt)
    logger.info("Result explanation generated (%d chars)", len(explanation))
    return explanation


def suggest_followups(question: str, results_summary: str, schema: str) -> list[str]:
    """Step 4: suggest 3 related follow-up questions."""
    prompt = prompts.FOLLOWUP_SUGGESTIONS_PROMPT.format(
        question=question,
        results_summary=results_summary,
        schema=schema,
    )

    json_schema = {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 3,
        "maxItems": 3,
    }

    response_text = _call_gemini(prompt, json_schema=json_schema)
    try:
        suggestions = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON from follow-up suggestions: %s", e)
        raise LLMError(f"Could not parse Gemini's response: {response_text[:200]}") from e

    if not isinstance(suggestions, list):
        raise LLMError("Follow-up suggestions response was not a JSON array.")

    logger.info("Generated %d follow-up suggestions", len(suggestions))
    return suggestions