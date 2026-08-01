"""
LLM layer for the NL2SQL pipeline using Google Gemini.
"""

import json
import logging
import os
import random
import time
from typing import Any

from google import genai
from google.genai import errors
from google.genai import types

import db
import prompts

logger = logging.getLogger(__name__)

# No guessed default: an unverified model name is worse than refusing to
# start. GEMINI_MODEL must be set explicitly to a model ID valid for the
# caller's Gemini API access (see .env.example) -- validate_config()
# below is the fail-fast check that enforces this at startup rather than
# letting a missing/invalid model surface as a confusing failure deep
# inside the first question a user asks.
MODEL = os.getenv("GEMINI_MODEL")
MAX_TOKENS = int(os.getenv("GEMINI_MAX_TOKENS", "2048"))
MAX_ATTEMPTS = int(os.getenv("GEMINI_MAX_ATTEMPTS", "4"))


class LLMError(Exception):
    """Single exception type exposed by the LLM layer."""


def validate_config() -> None:
    """
    Fail-fast startup check for the LLM layer's required configuration.

    Called once by the application at startup (app/main.py), before any
    question is accepted, so a missing or empty GEMINI_API_KEY /
    GEMINI_MODEL is reported clearly and immediately -- not as a
    confusing failure the first time a user asks a question.
    """

    missing = [
        name
        for name, value in (
            ("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY")),
            ("GEMINI_MODEL", MODEL),
        )
        if not value
    ]

    if missing:
        raise LLMError(
            "Missing required environment variable(s): "
            f"{', '.join(missing)}. Set them before starting the app "
            "(see .env.example)."
        )


def _get_client() -> genai.Client:
    """Create and return an authenticated Gemini client."""

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise LLMError("GEMINI_API_KEY environment variable is not set.")

    return genai.Client(api_key=api_key)


def _call_gemini(
    prompt: str,
    json_schema: dict[str, Any] | None = None,
) -> str:
    """
    Call Gemini.

    Structured JSON output is requested when json_schema is supplied.
    Temporary server failures are retried with exponential backoff.
    """

    if not isinstance(prompt, str) or not prompt.strip():
        raise LLMError("Gemini prompt cannot be empty.")

    client = _get_client()

    if json_schema is None:
        config = types.GenerateContentConfig(
            max_output_tokens=MAX_TOKENS,
        )
    else:
        config = types.GenerateContentConfig(
            max_output_tokens=MAX_TOKENS,
            response_mime_type="application/json",
            response_schema=json_schema,
        )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=config,
            )

            if not response.text:
                raise LLMError("Gemini returned an empty response.")

            return response.text.strip()

        except errors.ServerError as error:
            if attempt >= MAX_ATTEMPTS:
                logger.error(
                    "Gemini remained unavailable after %d attempts: %s",
                    MAX_ATTEMPTS,
                    error,
                )
                raise LLMError(
                    "Gemini is temporarily unavailable. "
                    f"The request failed after {MAX_ATTEMPTS} attempts: {error}"
                ) from error

            delay_seconds = (2 ** (attempt - 1)) + random.uniform(0.0, 1.0)

            logger.warning(
                "Gemini server error. Retrying in %.1f seconds "
                "(attempt %d/%d): %s",
                delay_seconds,
                attempt,
                MAX_ATTEMPTS,
                error,
            )

            time.sleep(delay_seconds)

        except errors.APIError as error:
            logger.error("Gemini API error: %s", error)
            raise LLMError(f"Gemini API request failed: {error}") from error

        except LLMError:
            raise

        except Exception as error:
            logger.exception("Unexpected Gemini API failure")
            raise LLMError(
                f"Gemini API call failed unexpectedly: {error}"
            ) from error

    raise LLMError("Gemini API call failed unexpectedly.")


def _get_database_metadata() -> dict[str, Any]:
    """
    Retrieve database metadata for date-aware SQL generation.

    The temporary fallback keeps SQL generation operational until
    db.get_database_metadata() has been added.
    """

    metadata_function = getattr(db, "get_database_metadata", None)

    if metadata_function is None:
        logger.warning(
            "db.get_database_metadata() is not implemented. "
            "Using unavailable metadata fallback."
        )

        return {
            "status": "unavailable",
            "message": (
                "Database metadata has not been supplied. Do not assume that "
                "the database is live. Use the supplied schema and question."
            ),
        }

    try:
        metadata = metadata_function()
    except Exception as error:
        logger.warning(
            "Could not retrieve database metadata: %s",
            error,
        )

        return {
            "status": "unavailable",
            "message": (
                "Database metadata could not be retrieved. Do not assume that "
                "the database is live. Use the supplied schema and question."
            ),
        }

    if not isinstance(metadata, dict):
        logger.warning(
            "db.get_database_metadata() returned %s instead of a dictionary.",
            type(metadata).__name__,
        )

        return {
            "status": "unavailable",
            "message": (
                "Database metadata was returned in an unsupported format."
            ),
        }

    return metadata


def understand_question(question: str, schema: str) -> dict[str, Any]:
    """
    Step 1: extract intent, entities, filters, assumptions, and ambiguity.
    """

    if not isinstance(question, str) or not question.strip():
        raise LLMError("Question cannot be empty.")

    if not isinstance(schema, str) or not schema.strip():
        raise LLMError("Database schema cannot be empty.")

    prompt = prompts.QUESTION_UNDERSTANDING_PROMPT.format(
        schema=schema,
        question=question,
    )

    json_schema = {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
            },
            "entities": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
            "time_filter": {
                "type": "string",
                "nullable": True,
            },
            "aggregation": {
                "type": "string",
                "nullable": True,
            },
            "assumptions": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
            "ambiguity": {
                "type": "boolean",
            },
        },
        "required": [
            "intent",
            "entities",
            "time_filter",
            "aggregation",
            "assumptions",
            "ambiguity",
        ],
    }

    response_text = _call_gemini(
        prompt,
        json_schema=json_schema,
    )

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as error:
        logger.error(
            "Failed to parse JSON from question understanding: %s",
            error,
        )
        raise LLMError(
            f"Could not parse Gemini's response: {response_text[:200]}"
        ) from error

    if not isinstance(result, dict):
        raise LLMError(
            "Question-understanding response was not a JSON object."
        )

    logger.info(
        "Question understood: intent=%s",
        result.get("intent"),
    )

    return result


def generate_sql(
    question: str,
    schema: str,
    understanding: dict[str, Any],
) -> str:
    """
    Step 2: generate a safe, read-only PostgreSQL query.

    Database metadata is injected into the prompt so relative dates can be
    interpreted against the available dataset rather than the system date.
    """

    if not isinstance(question, str) or not question.strip():
        raise LLMError("Question cannot be empty.")

    if not isinstance(schema, str) or not schema.strip():
        raise LLMError("Database schema cannot be empty.")

    if not isinstance(understanding, dict):
        raise LLMError("Question understanding must be a dictionary.")

    database_metadata = _get_database_metadata()

    prompt = prompts.SQL_GENERATION_PROMPT.format(
        schema=schema,
        database_metadata=json.dumps(
            database_metadata,
            indent=2,
            default=str,
        ),
        question=question,
        understanding=json.dumps(
            understanding,
            indent=2,
            default=str,
        ),
    )

    sql = _call_gemini(prompt)

    # Defensive cleanup in case the model ignores the no-markdown rule.
    if sql.startswith("```"):
        parts = sql.split("```")

        if len(parts) >= 2:
            sql = parts[1]
            sql = sql.removeprefix("sql").strip()
            sql = sql.removeprefix("postgresql").strip()

    sql = sql.strip()

    if not sql:
        raise LLMError("Gemini generated an empty SQL query.")

    logger.info("SQL generated (%d chars)", len(sql))

    return sql

def regenerate_sql(
    question: str,
    schema: str,
    understanding: dict[str, Any],
    previous_sql: str,
    failure_type: str,
    error_message: str,
) -> str:
    """
    Regenerate SQL after validation or database execution failure.

    The correction attempt receives the original question, schema,
    metadata, previous SQL, and exact failure details.
    """

    if not isinstance(question, str) or not question.strip():
        raise LLMError("Question cannot be empty.")

    if not isinstance(schema, str) or not schema.strip():
        raise LLMError("Database schema cannot be empty.")

    if not isinstance(understanding, dict):
        raise LLMError("Question understanding must be a dictionary.")

    if not isinstance(previous_sql, str) or not previous_sql.strip():
        raise LLMError("Previous SQL cannot be empty.")

    if failure_type not in {
        "validation_error",
        "database_error",
    }:
        raise LLMError(
            "Failure type must be validation_error or database_error."
        )

    if not isinstance(error_message, str) or not error_message.strip():
        raise LLMError("Error message cannot be empty.")

    database_metadata = _get_database_metadata()

    prompt = prompts.SQL_REGENERATION_PROMPT.format(
        schema=schema,
        database_metadata=json.dumps(
            database_metadata,
            indent=2,
            default=str,
        ),
        question=question,
        understanding=json.dumps(
            understanding,
            indent=2,
            default=str,
        ),
        previous_sql=previous_sql,
        failure_type=failure_type,
        error_message=error_message,
    )

    corrected_sql = _call_gemini(prompt)

    if corrected_sql.startswith("```"):
        parts = corrected_sql.split("```")

        if len(parts) >= 2:
            corrected_sql = parts[1]
            corrected_sql = corrected_sql.removeprefix("sql").strip()
            corrected_sql = corrected_sql.removeprefix(
                "postgresql"
            ).strip()

    corrected_sql = corrected_sql.strip()

    if not corrected_sql:
        raise LLMError(
            "Gemini generated an empty corrected SQL query."
        )

    logger.info(
        "SQL regenerated after %s (%d chars)",
        failure_type,
        len(corrected_sql),
    )

    return corrected_sql

def explain_results(
    question: str,
    sql: str,
    columns: list[str],
    rows: list[tuple[Any, ...]],
) -> str:
    """
    Step 3: turn query results into a plain-English explanation.
    """

    if not isinstance(question, str) or not question.strip():
        raise LLMError("Question cannot be empty.")

    if not isinstance(sql, str) or not sql.strip():
        raise LLMError("Executed SQL cannot be empty.")

    preview_rows = rows[:20]

    if columns:
        result_lines = [", ".join(str(column) for column in columns)]
    else:
        result_lines = []

    result_lines.extend(
        ", ".join(str(value) for value in row)
        for row in preview_rows
    )

    results_text = "\n".join(result_lines)

    if not results_text:
        results_text = "No rows were returned."

    prompt = prompts.RESULT_EXPLANATION_PROMPT.format(
        question=question,
        sql=sql,
        row_count=len(rows),
        results=results_text,
    )

    explanation = _call_gemini(prompt).strip()

    if not explanation:
        raise LLMError("Gemini generated an empty result explanation.")

    logger.info(
        "Result explanation generated (%d chars)",
        len(explanation),
    )

    return explanation


def suggest_followups(
    question: str,
    results_summary: str,
    schema: str,
) -> list[str]:
    """
    Step 4: suggest exactly three related follow-up questions.
    """

    if not isinstance(question, str) or not question.strip():
        raise LLMError("Question cannot be empty.")

    if not isinstance(schema, str) or not schema.strip():
        raise LLMError("Database schema cannot be empty.")

    prompt = prompts.FOLLOWUP_SUGGESTIONS_PROMPT.format(
        question=question,
        results_summary=results_summary,
        schema=schema,
    )

    json_schema = {
        "type": "array",
        "items": {
            "type": "string",
        },
        "minItems": 3,
        "maxItems": 3,
    }

    response_text = _call_gemini(
        prompt,
        json_schema=json_schema,
    )

    try:
        suggestions = json.loads(response_text)
    except json.JSONDecodeError as error:
        logger.error(
            "Failed to parse JSON from follow-up suggestions: %s",
            error,
        )
        raise LLMError(
            f"Could not parse Gemini's response: {response_text[:200]}"
        ) from error

    if not isinstance(suggestions, list):
        raise LLMError(
            "Follow-up suggestions response was not a JSON array."
        )

    if len(suggestions) != 3:
        raise LLMError(
            "Gemini did not return exactly three follow-up suggestions."
        )

    if not all(
        isinstance(suggestion, str) and suggestion.strip()
        for suggestion in suggestions
    ):
        raise LLMError(
            "Gemini returned an invalid follow-up suggestion."
        )

    cleaned_suggestions = [
        suggestion.strip()
        for suggestion in suggestions
    ]

    logger.info(
        "Generated %d follow-up suggestions",
        len(cleaned_suggestions),
    )

    return cleaned_suggestions