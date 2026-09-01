"""
Gemini-specific implementation of the LLMProvider interface.

Every Gemini SDK import, Gemini-specific exception class, Gemini
configuration constant, and the 429/5xx retry logic lives in this one
module -- nothing outside app/llm/gemini_provider.py may import
google.genai. This is the only file that changes when Gemini's SDK or
error handling changes, and the only file a second provider (e.g. Groq)
would sit alongside, not modify.
"""

import logging
import os
import random
import time
from typing import Any

from google import genai
from google.genai import errors
from google.genai import types

from .base import LLMError, LLMProvider

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

# Explicit request timeout -- previously absent entirely, relying on
# whatever the SDK's own default is (if any). types.HttpOptions.timeout
# is in milliseconds; confirmed against the installed SDK's actual field
# definitions before using it, not assumed.
GEMINI_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("GEMINI_REQUEST_TIMEOUT_SECONDS", "30")
)

# 429 (RESOURCE_EXHAUSTED) gets its own small, separate retry budget from
# MAX_ATTEMPTS above, which governs 5xx ServerError retries. Deliberately
# small so a rate-limited question fails fast rather than holding the
# Streamlit UI for minutes.
GEMINI_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("GEMINI_RATE_LIMIT_MAX_ATTEMPTS", "2"))
GEMINI_RATE_LIMIT_MAX_DELAY_SECONDS = float(
    os.getenv("GEMINI_RATE_LIMIT_MAX_DELAY_SECONDS", "10")
)


def validate_config() -> None:
    """
    Fail-fast startup check for Gemini's required configuration.

    Called once by the application at startup (app/main.py, via
    app/llm/factory.py), before any question is accepted, so a missing
    or empty GEMINI_API_KEY / GEMINI_MODEL is reported clearly and
    immediately -- not as a confusing failure the first time a user asks
    a question.
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


def _extract_retry_delay_seconds(error: "errors.ClientError") -> float | None:
    """
    Best-effort extraction of google.rpc.RetryInfo.retryDelay from a 429
    response, if Gemini supplied one.

    The exact shape of error.details is not something this codebase can
    verify without deliberately exhausting a real quota against a live
    key, so this is deliberately defensive: any unexpected shape returns
    None (falls back to bounded backoff in the caller) rather than
    raising or assuming a structure that may not hold.
    """

    try:
        details = error.details

        if isinstance(details, dict) and "error" in details:
            details = details["error"]

        for detail in (details or {}).get("details", []):
            if "RetryInfo" in str(detail.get("@type", "")):
                raw_delay = detail.get("retryDelay", "")

                if isinstance(raw_delay, str) and raw_delay.endswith("s"):
                    return float(raw_delay[:-1])
    except Exception:
        logger.debug(
            "Could not parse RetryInfo from a 429 response; "
            "falling back to bounded backoff.",
            exc_info=True,
        )

    return None


class GeminiProvider(LLMProvider):
    """
    Structured JSON output is requested when json_schema is supplied.
    5xx server errors are retried with exponential backoff (MAX_ATTEMPTS).
    429 rate-limit/quota errors get their own smaller, bounded retry
    budget (GEMINI_RATE_LIMIT_MAX_ATTEMPTS) -- see the ClientError branch
    below. Every request carries an explicit timeout.
    """

    def generate(
        self,
        prompt: str,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise LLMError("Gemini prompt cannot be empty.")

        client = _get_client()

        http_options = types.HttpOptions(
            timeout=int(GEMINI_REQUEST_TIMEOUT_SECONDS * 1000)
        )

        if json_schema is None:
            config = types.GenerateContentConfig(
                max_output_tokens=MAX_TOKENS,
                http_options=http_options,
            )
        else:
            config = types.GenerateContentConfig(
                max_output_tokens=MAX_TOKENS,
                response_mime_type="application/json",
                response_schema=json_schema,
                http_options=http_options,
            )

        rate_limit_attempts = 0

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

            except errors.ClientError as error:
                if error.code != 429:
                    logger.error("Gemini client error: %s", error)
                    raise LLMError(f"Gemini API request failed: {error}") from error

                rate_limit_attempts += 1

                retry_delay = _extract_retry_delay_seconds(error)

                if retry_delay is not None:
                    # Respect the server's suggestion, but cap it -- a
                    # suggestion longer than the cap will not resolve on
                    # a short retry, so treat it as exhausted (fail fast)
                    # rather than actually holding the UI that long.
                    is_transient = retry_delay <= GEMINI_RATE_LIMIT_MAX_DELAY_SECONDS
                    delay_seconds = min(
                        retry_delay,
                        GEMINI_RATE_LIMIT_MAX_DELAY_SECONDS,
                    )
                else:
                    # No RetryInfo supplied -- bounded backoff, a
                    # separate (smaller) schedule from the ServerError
                    # one below.
                    is_transient = True
                    delay_seconds = min(
                        2 ** (rate_limit_attempts - 1),
                        GEMINI_RATE_LIMIT_MAX_DELAY_SECONDS,
                    )

                exhausted = (
                    not is_transient
                    or rate_limit_attempts >= GEMINI_RATE_LIMIT_MAX_ATTEMPTS
                )

                if exhausted:
                    logger.error(
                        "Gemini rate limit or quota exceeded after %d "
                        "attempt(s) (retryDelay=%s, transient=%s): %s",
                        rate_limit_attempts,
                        retry_delay,
                        is_transient,
                        error,
                    )
                    raise LLMError(
                        "Gemini rate limit or quota exceeded after "
                        f"{rate_limit_attempts} attempt(s): {error}"
                    ) from error

                logger.warning(
                    "Gemini rate limited (429). Retrying in %.1f seconds "
                    "(attempt %d/%d, retryDelay=%s): %s",
                    delay_seconds,
                    rate_limit_attempts,
                    GEMINI_RATE_LIMIT_MAX_ATTEMPTS,
                    retry_delay,
                    error,
                )

                time.sleep(delay_seconds)
                continue

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


def get_provider() -> GeminiProvider:
    return GeminiProvider()
