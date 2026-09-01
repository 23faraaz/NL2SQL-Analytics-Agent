"""
Groq-specific implementation of the LLMProvider interface.

Every Groq API call, Groq-specific error mapping, and Groq configuration
constant lives in this one module -- nothing outside this file may
reference Groq's REST request/response shape directly. This is the file
a third provider would sit alongside, not modify.

Groq's chat completions endpoint is OpenAI-compatible REST/JSON
(https://console.groq.com/docs/api-reference); there is no official groq
SDK dependency here since a single JSON POST doesn't need one -- requests
is enough and is already an existing project dependency.

Model: openai/gpt-oss-20b is the default recommendation (see
.env.example) -- of Groq's models, strict-mode JSON Schema structured
outputs (constrained decoding, not just "valid JSON") are currently only
supported on the openai/gpt-oss-20b and openai/gpt-oss-120b models
(https://console.groq.com/docs/structured-outputs, verified against
Groq's live docs before choosing). gpt-oss-20b is the faster of the two
with a 128K context window, more than this app needs. GROQ_MODEL can be
overridden to gpt-oss-120b for higher accuracy at lower throughput.
"""

import json
import logging
import os
import random
import time
from typing import Any

import jsonschema
import requests

from .base import LLMError, LLMProvider

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Mirrors gemini_provider.py's "no guessed default" policy: an
# unverified model name is worse than refusing to start.
MODEL = os.getenv("GROQ_MODEL")
MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "2048"))
MAX_ATTEMPTS = int(os.getenv("GROQ_MAX_ATTEMPTS", "4"))

GROQ_REQUEST_TIMEOUT_SECONDS = float(os.getenv("GROQ_REQUEST_TIMEOUT_SECONDS", "30"))

# Mirrors gemini_provider.py's separate, smaller 429 retry budget --
# deliberately small so a rate-limited question fails fast rather than
# holding the Streamlit UI for minutes.
GROQ_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("GROQ_RATE_LIMIT_MAX_ATTEMPTS", "2"))
GROQ_RATE_LIMIT_MAX_DELAY_SECONDS = float(
    os.getenv("GROQ_RATE_LIMIT_MAX_DELAY_SECONDS", "10")
)


def validate_config() -> None:
    """
    Fail-fast startup check for Groq's required configuration. Called via
    app/llm/factory.py's validate_config() when LLM_PROVIDER=groq.
    """

    missing = [
        name
        for name, value in (
            ("GROQ_API_KEY", os.environ.get("GROQ_API_KEY")),
            ("GROQ_MODEL", MODEL),
        )
        if not value
    ]

    if missing:
        raise LLMError(
            "Missing required environment variable(s): "
            f"{', '.join(missing)}. Set them before starting the app "
            "(see .env.example)."
        )


def _get_api_key() -> str:
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise LLMError("GROQ_API_KEY environment variable is not set.")

    return api_key


def _translate_schema_for_strict_mode(
    json_schema_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Translate the pipeline's Gemini/OpenAPI-flavoured schema (uses
    "nullable": true alongside a single "type") into the dialect Groq's
    strict-mode structured outputs require: nullable fields use
    "type": [T, "null"] instead, and the object needs
    "additionalProperties": false with every property listed in
    "required" (strict mode does not support a smaller "required" list
    than the full property set).

    This only handles the flat, one-level object shape
    understand_and_generate_sql()'s schema actually uses -- not a
    general-purpose JSON Schema dialect transpiler.
    """

    properties = json_schema_dict.get("properties", {})
    translated_properties: dict[str, Any] = {}

    for name, spec in properties.items():
        spec = dict(spec)

        if spec.pop("nullable", False):
            original_type = spec.get("type")

            if isinstance(original_type, str):
                spec["type"] = [original_type, "null"]

        translated_properties[name] = spec

    return {
        "type": "object",
        "properties": translated_properties,
        "required": list(translated_properties.keys()),
        "additionalProperties": False,
    }


def _extract_retry_after_seconds(response: "requests.Response") -> float | None:
    """
    Best-effort extraction of Groq's documented `retry-after` response
    header (seconds) on a 429. Defensive: any missing/unparseable header
    returns None (falls back to bounded backoff in the caller) rather
    than raising.
    """

    raw_value = response.headers.get("retry-after")

    if raw_value is None:
        return None

    try:
        return float(raw_value)
    except (TypeError, ValueError):
        logger.debug(
            "Could not parse Groq's retry-after header %r; "
            "falling back to bounded backoff.",
            raw_value,
        )
        return None


def _validate_structured_json(content: str, schema: dict[str, Any]) -> str:
    """
    Parse and schema-validate a structured Groq response before it is
    trusted by the rest of the codebase. Groq's strict mode is
    constrained decoding, not a hard guarantee (Groq's own docs note it
    can still return errors on unsupported schemas) -- unlike this
    codebase's existing trust in Gemini's response_schema, Groq's output
    is verified locally so malformed or schema-invalid JSON never reaches
    the SQL pipeline.
    """

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        logger.error("Groq structured response was not valid JSON: %s", error)
        raise LLMError(f"Groq returned malformed JSON: {content[:200]}") from error

    try:
        jsonschema.validate(instance=parsed, schema=schema)
    except jsonschema.ValidationError as error:
        logger.error(
            "Groq structured response failed schema validation: %s",
            error,
        )
        raise LLMError(
            f"Groq response did not match the expected schema: {error.message}"
        ) from error

    return content


class GroqProvider(LLMProvider):
    """
    Structured JSON output uses Groq's strict-mode json_schema response
    format; the parsed response is additionally validated locally against
    the same (translated) schema before generate() returns -- see
    _validate_structured_json(). 429s are retried using Groq's documented
    `retry-after` header, with the same bounded-attempts/capped-delay
    policy as gemini_provider.py. 5xx responses get their own bounded
    exponential backoff, separate from the 429 budget, also mirroring
    gemini_provider.py. Every request carries an explicit timeout.
    """

    def generate(
        self,
        prompt: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise LLMError("Groq prompt cannot be empty.")

        api_key = _get_api_key()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_TOKENS,
        }

        translated_schema: dict[str, Any] | None = None

        if json_schema is not None:
            translated_schema = _translate_schema_for_strict_mode(json_schema)
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "nl2sql_response",
                    "strict": True,
                    "schema": translated_schema,
                },
            }

        rate_limit_attempts = 0

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = requests.post(
                    GROQ_API_URL,
                    headers=headers,
                    json=body,
                    timeout=GROQ_REQUEST_TIMEOUT_SECONDS,
                )
            except requests.exceptions.Timeout as error:
                logger.error("Groq request timed out: %s", error)
                raise LLMError(f"Groq API request timed out: {error}") from error
            except requests.exceptions.RequestException as error:
                logger.error("Groq request failed: %s", error)
                raise LLMError(f"Groq API request failed: {error}") from error

            if response.status_code == 429:
                rate_limit_attempts += 1
                retry_after = _extract_retry_after_seconds(response)

                if retry_after is not None:
                    is_transient = retry_after <= GROQ_RATE_LIMIT_MAX_DELAY_SECONDS
                    delay_seconds = min(retry_after, GROQ_RATE_LIMIT_MAX_DELAY_SECONDS)
                else:
                    is_transient = True
                    delay_seconds = min(
                        2 ** (rate_limit_attempts - 1),
                        GROQ_RATE_LIMIT_MAX_DELAY_SECONDS,
                    )

                exhausted = (
                    not is_transient
                    or rate_limit_attempts >= GROQ_RATE_LIMIT_MAX_ATTEMPTS
                )

                if exhausted:
                    logger.error(
                        "Groq rate limit or quota exceeded after %d "
                        "attempt(s) (retry-after=%s, transient=%s): %s",
                        rate_limit_attempts,
                        retry_after,
                        is_transient,
                        response.text[:500],
                    )
                    raise LLMError(
                        "Groq rate limit or quota exceeded after "
                        f"{rate_limit_attempts} attempt(s)."
                    )

                logger.warning(
                    "Groq rate limited (429). Retrying in %.1f seconds "
                    "(attempt %d/%d, retry-after=%s).",
                    delay_seconds,
                    rate_limit_attempts,
                    GROQ_RATE_LIMIT_MAX_ATTEMPTS,
                    retry_after,
                )

                time.sleep(delay_seconds)
                continue

            if response.status_code >= 500:
                if attempt >= MAX_ATTEMPTS:
                    logger.error(
                        "Groq remained unavailable after %d attempts: %s",
                        MAX_ATTEMPTS,
                        response.text[:500],
                    )
                    raise LLMError(
                        "Groq is temporarily unavailable. "
                        f"The request failed after {MAX_ATTEMPTS} attempts."
                    )

                delay_seconds = (2 ** (attempt - 1)) + random.uniform(0.0, 1.0)

                logger.warning(
                    "Groq server error (%d). Retrying in %.1f seconds "
                    "(attempt %d/%d).",
                    response.status_code,
                    delay_seconds,
                    attempt,
                    MAX_ATTEMPTS,
                )

                time.sleep(delay_seconds)
                continue

            if response.status_code >= 400:
                logger.error(
                    "Groq client error (%d): %s",
                    response.status_code,
                    response.text[:500],
                )
                raise LLMError(
                    f"Groq API request failed with status {response.status_code}."
                )

            try:
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as error:
                logger.error("Unexpected Groq response shape: %s", error)
                raise LLMError("Groq returned an unexpected response shape.") from error

            if not content or not content.strip():
                raise LLMError("Groq returned an empty response.")

            content = content.strip()

            if translated_schema is not None:
                content = _validate_structured_json(content, translated_schema)

            return content

        raise LLMError("Groq API call failed unexpectedly.")


def get_provider() -> GroqProvider:
    return GroqProvider()
