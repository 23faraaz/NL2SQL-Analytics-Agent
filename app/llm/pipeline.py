"""
Provider-independent NL2SQL orchestration.

Every function here calls the configured LLMProvider through
app/llm/factory.py's get_provider() -- never a concrete provider or
google.genai directly. That is what lets app/main.py, and this module,
stay unaware of which provider is actually configured.
"""

import json
import logging
from typing import Any

import db
import prompts

from . import factory
from .base import LLMError

logger = logging.getLogger(__name__)


def _generate(prompt: str, json_schema: dict[str, Any] | None = None) -> str:
    provider = factory.get_provider()
    return provider.generate(prompt, json_schema=json_schema)


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
            "message": ("Database metadata was returned in an unsupported format."),
        }

    return metadata


def understand_and_generate_sql(
    question: str,
    schema: str,
) -> tuple[dict[str, Any], str]:
    """
    Steps 1+2 combined into a single provider call: extract intent/
    entities/time_filter/aggregation/assumptions/ambiguity AND generate
    the SQL query that answers the question, in one round trip instead
    of two.

    Previously understand_question() and generate_sql() were always both
    called, in sequence, for every question -- this halves the LLM call
    count for the common case, directly reducing pressure on the API
    quota. Database metadata is injected into the prompt so relative
    dates can be interpreted against the available dataset rather than
    the system date, same as generate_sql() did before.
    """

    if not isinstance(question, str) or not question.strip():
        raise LLMError("Question cannot be empty.")

    if not isinstance(schema, str) or not schema.strip():
        raise LLMError("Database schema cannot be empty.")

    database_metadata = _get_database_metadata()

    prompt = prompts.UNDERSTAND_AND_GENERATE_SQL_PROMPT.format(
        schema=schema,
        database_metadata=json.dumps(
            database_metadata,
            indent=2,
            default=str,
        ),
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
            "sql": {
                "type": "string",
            },
        },
        "required": [
            "intent",
            "entities",
            "time_filter",
            "aggregation",
            "assumptions",
            "ambiguity",
            "sql",
        ],
    }

    response_text = _generate(
        prompt,
        json_schema=json_schema,
    )

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as error:
        logger.error(
            "Failed to parse JSON from understand_and_generate_sql: %s",
            error,
        )
        raise LLMError(
            f"Could not parse Gemini's response: {response_text[:200]}"
        ) from error

    if not isinstance(result, dict):
        raise LLMError("Understand-and-generate-SQL response was not a JSON object.")

    sql = result.pop("sql", None)

    if not isinstance(sql, str) or not sql.strip():
        raise LLMError("Gemini generated an empty SQL query.")

    sql = sql.strip()

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

    understanding = result

    logger.info(
        "Question understood and SQL generated in one call: "
        "intent=%s (%d chars SQL)",
        understanding.get("intent"),
        len(sql),
    )

    return understanding, sql


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
        raise LLMError("Failure type must be validation_error or database_error.")

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

    corrected_sql = _generate(prompt)

    if corrected_sql.startswith("```"):
        parts = corrected_sql.split("```")

        if len(parts) >= 2:
            corrected_sql = parts[1]
            corrected_sql = corrected_sql.removeprefix("sql").strip()
            corrected_sql = corrected_sql.removeprefix("postgresql").strip()

    corrected_sql = corrected_sql.strip()

    if not corrected_sql:
        raise LLMError("Gemini generated an empty corrected SQL query.")

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

    result_lines.extend(", ".join(str(value) for value in row) for row in preview_rows)

    results_text = "\n".join(result_lines)

    if not results_text:
        results_text = "No rows were returned."

    prompt = prompts.RESULT_EXPLANATION_PROMPT.format(
        question=question,
        sql=sql,
        row_count=len(rows),
        results=results_text,
    )

    explanation = _generate(prompt).strip()

    if not explanation:
        raise LLMError("Gemini generated an empty result explanation.")

    logger.info(
        "Result explanation generated (%d chars)",
        len(explanation),
    )

    return explanation


# Deterministic follow-up candidates, keyed by the substring of an
# `understanding["entities"]` value that should trigger them. Not an
# LLM call: this is a curated mapping over the commerce schema's real
# entities (customers, orders, products, revenue/sales, payments,
# suppliers, categories), not a generic/invented list.
_FOLLOWUP_ENTITY_TEMPLATES: dict[str, list[str]] = {
    "customer": [
        "Who are our top 10 customers by lifetime revenue?",
        "How many new customers did we acquire last month?",
    ],
    "order": [
        "How does this compare to the previous period?",
        "What is the average order value?",
    ],
    "product": [
        "Which products generated the most revenue?",
        "Which products have the lowest sales?",
    ],
    "revenue": [
        "How does this compare to the previous period?",
    ],
    "sales": [
        "How does this compare to the previous period?",
    ],
    "payment": [
        "What payment methods are most commonly used?",
    ],
    "supplier": [
        "Which suppliers do we source the most products from?",
    ],
    "category": [
        "Which category generates the most revenue?",
    ],
}


def suggest_followups(
    question: str,
    understanding: dict[str, Any],
    fallback_pool: list[str],
) -> list[str]:
    """
    Deterministic replacement for the former LLM-based follow-up
    suggestion call (previously a fourth Gemini round trip on every
    question). Templates candidate follow-ups from the entities the
    question was already understood to involve
    (understanding["entities"], produced by
    understand_and_generate_sql() -- no extra API call needed), then
    tops up to 3 from fallback_pool (the caller's own starter-question
    pool) if there are not enough entity matches.

    No API call, so this cannot raise LLMError -- there is no provider
    outage to handle for a pure function.
    """

    entities = [
        str(entity).lower()
        for entity in (understanding.get("entities") or [])
        if isinstance(entity, (str, int, float))
    ]

    candidates: list[str] = []

    for entity in entities:
        for key, templates in _FOLLOWUP_ENTITY_TEMPLATES.items():
            if key not in entity:
                continue

            for template in templates:
                if template not in candidates:
                    candidates.append(template)

    normalized_question = question.strip().lower()

    for fallback_question in fallback_pool:
        if len(candidates) >= 3:
            break

        if fallback_question.strip().lower() == normalized_question:
            continue

        if fallback_question not in candidates:
            candidates.append(fallback_question)

    suggestions = candidates[:3]

    logger.info(
        "Generated %d deterministic follow-up suggestions",
        len(suggestions),
    )

    return suggestions
