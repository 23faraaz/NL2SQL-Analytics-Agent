"""
Tests for the app/llm package -- focused on the behaviour added in the
Gemini 429-handling and reduced-call-count change:

- gemini_provider._extract_retry_delay_seconds(): pure best-effort
  RetryInfo parsing.
- llm.suggest_followups(): pure deterministic follow-up templating (no
  API call, so no mocking required).
- GeminiProvider.generate(): 429 retry/backoff behaviour, bounded and
  non-infinite, via a monkeypatched client so no real network call is
  made.

No database or live Gemini credentials are required.

Provider-internal names (retry/backoff constants, _get_client,
_extract_retry_delay_seconds, the retry loop itself) live in
llm.gemini_provider now that app/llm.py was split into a package -- this
file was updated only for that move (import path and call shape:
llm._call_gemini(...) became
gemini_provider.GeminiProvider().generate(...)), not for any behaviour
change. suggest_followups() and LLMError are still reached via the
top-level llm package, exactly as before, since they remain part of its
public API.
"""

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import llm  # noqa: E402
from llm import gemini_provider  # noqa: E402
from google.genai import errors  # noqa: E402


# ---------------------------------------------------------------------
# _extract_retry_delay_seconds
# ---------------------------------------------------------------------


def _client_error_with_details(details_body: dict) -> errors.ClientError:
    return errors.ClientError(429, details_body)


def test_extract_retry_delay_parses_wrapped_retry_info():
    error = _client_error_with_details(
        {
            "error": {
                "code": 429,
                "message": "rate limited",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "2.5s",
                    }
                ],
            }
        }
    )

    assert gemini_provider._extract_retry_delay_seconds(error) == pytest.approx(2.5)


def test_extract_retry_delay_parses_unwrapped_retry_info():
    error = _client_error_with_details(
        {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "7s",
                }
            ],
        }
    )

    assert gemini_provider._extract_retry_delay_seconds(error) == pytest.approx(7.0)


def test_extract_retry_delay_returns_none_when_absent():
    error = _client_error_with_details(
        {
            "error": {
                "code": 429,
                "message": "rate limited",
                "status": "RESOURCE_EXHAUSTED",
                "details": [],
            }
        }
    )

    assert gemini_provider._extract_retry_delay_seconds(error) is None


def test_extract_retry_delay_never_raises_on_malformed_shape():
    error = _client_error_with_details(
        {
            "error": {
                "code": 429,
                "details": [{"@type": "RetryInfo", "retryDelay": None}],
            }
        }
    )

    assert gemini_provider._extract_retry_delay_seconds(error) is None


def test_extract_retry_delay_never_raises_when_details_is_not_a_dict():
    error = errors.ClientError(429, [{"unexpected": "shape"}])

    assert gemini_provider._extract_retry_delay_seconds(error) is None


# ---------------------------------------------------------------------
# suggest_followups
# ---------------------------------------------------------------------

FALLBACK_POOL = [
    "How much revenue did we generate this month?",
    "Who are our top ten customers by revenue?",
    "Compare sales this month with last month.",
    "Which products generated the most revenue?",
]


def test_suggest_followups_never_raises_llm_error():
    understanding = {"entities": ["customers"]}

    followups = llm.suggest_followups(
        "Who are our top customers?",
        understanding,
        FALLBACK_POOL,
    )

    assert isinstance(followups, list)


def test_suggest_followups_matches_entity_templates():
    understanding = {"entities": ["customer"]}

    followups = llm.suggest_followups(
        "How many customers do we have?",
        understanding,
        FALLBACK_POOL,
    )

    assert "Who are our top 10 customers by lifetime revenue?" in followups
    assert "How many new customers did we acquire last month?" in followups


def test_suggest_followups_returns_at_most_three():
    understanding = {
        "entities": ["customer", "order", "product", "revenue", "payment"]
    }

    followups = llm.suggest_followups(
        "Give me an overview",
        understanding,
        FALLBACK_POOL,
    )

    assert len(followups) <= 3


def test_suggest_followups_tops_up_from_fallback_pool_when_no_entities():
    understanding = {"entities": []}

    followups = llm.suggest_followups(
        "Some question unrelated to any entity",
        understanding,
        FALLBACK_POOL,
    )

    assert len(followups) == 3
    assert all(item in FALLBACK_POOL for item in followups)


def test_suggest_followups_excludes_the_original_question():
    understanding = {"entities": []}
    original = FALLBACK_POOL[0]

    followups = llm.suggest_followups(
        original,
        understanding,
        FALLBACK_POOL,
    )

    assert original not in followups


def test_suggest_followups_handles_non_string_entities_without_raising():
    understanding = {"entities": [None, 42, {"nested": "object"}, "product"]}

    followups = llm.suggest_followups(
        "Which products sell best?",
        understanding,
        FALLBACK_POOL,
    )

    assert isinstance(followups, list)
    assert "Which products generated the most revenue?" in followups


# ---------------------------------------------------------------------
# GeminiProvider.generate() 429 retry/backoff behaviour
# ---------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeModels:
    def __init__(self, effects: list):
        self._effects = list(effects)
        self.call_count = 0

    def generate_content(self, *, model, contents, config):
        self.call_count += 1

        if not self._effects:
            raise AssertionError("No more fake effects queued")

        effect = self._effects.pop(0)

        if isinstance(effect, Exception):
            raise effect

        return effect


class _FakeClient:
    def __init__(self, effects: list):
        self.models = _FakeModels(effects)


def _rate_limited_error(retry_delay: str | None) -> errors.ClientError:
    details: dict = {
        "error": {
            "code": 429,
            "message": "rate limited",
            "status": "RESOURCE_EXHAUSTED",
            "details": [],
        }
    }

    if retry_delay is not None:
        details["error"]["details"] = [
            {
                "@type": "type.googleapis.com/google.rpc.RetryInfo",
                "retryDelay": retry_delay,
            }
        ]

    return errors.ClientError(429, details)


def _patch_no_sleep(monkeypatch):
    monkeypatch.setattr(gemini_provider.time, "sleep", lambda seconds: None)


def test_call_gemini_retries_bounded_times_then_raises(monkeypatch):
    _patch_no_sleep(monkeypatch)

    fake_client = _FakeClient(
        [
            _rate_limited_error(None)
            for _ in range(gemini_provider.GEMINI_RATE_LIMIT_MAX_ATTEMPTS)
        ]
    )
    monkeypatch.setattr(gemini_provider, "_get_client", lambda: fake_client)

    with pytest.raises(llm.LLMError):
        gemini_provider.GeminiProvider().generate("some prompt")

    assert (
        fake_client.models.call_count
        == gemini_provider.GEMINI_RATE_LIMIT_MAX_ATTEMPTS
    )


def test_call_gemini_succeeds_after_transient_429_with_retry_info(monkeypatch):
    _patch_no_sleep(monkeypatch)

    fake_client = _FakeClient(
        [
            _rate_limited_error("0.1s"),
            _FakeResponse("final answer"),
        ]
    )
    monkeypatch.setattr(gemini_provider, "_get_client", lambda: fake_client)

    result = gemini_provider.GeminiProvider().generate("some prompt")

    assert result == "final answer"
    assert fake_client.models.call_count == 2


def test_call_gemini_fails_fast_when_retry_delay_exceeds_cap(monkeypatch):
    _patch_no_sleep(monkeypatch)

    huge_delay = f"{gemini_provider.GEMINI_RATE_LIMIT_MAX_DELAY_SECONDS + 60}s"
    fake_client = _FakeClient([_rate_limited_error(huge_delay)])
    monkeypatch.setattr(gemini_provider, "_get_client", lambda: fake_client)

    with pytest.raises(llm.LLMError):
        gemini_provider.GeminiProvider().generate("some prompt")

    assert fake_client.models.call_count == 1


def test_call_gemini_non_429_client_error_fails_immediately(monkeypatch):
    _patch_no_sleep(monkeypatch)

    not_found = errors.ClientError(
        404,
        {"error": {"code": 404, "message": "not found", "status": "NOT_FOUND"}},
    )
    fake_client = _FakeClient([not_found])
    monkeypatch.setattr(gemini_provider, "_get_client", lambda: fake_client)

    with pytest.raises(llm.LLMError):
        gemini_provider.GeminiProvider().generate("some prompt")

    assert fake_client.models.call_count == 1


# ---------------------------------------------------------------------
# Request timeout: confirm it is not just a defined constant but is
# actually threaded into the request the SDK sends.
# ---------------------------------------------------------------------


class _ConfigCapturingModels:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.seen_configs: list = []

    def generate_content(self, *, model, contents, config):
        self.seen_configs.append(config)
        return _FakeResponse(self._response_text)


class _ConfigCapturingClient:
    def __init__(self, response_text: str):
        self.models = _ConfigCapturingModels(response_text)


def test_call_gemini_applies_configured_timeout_without_json_schema(monkeypatch):
    _patch_no_sleep(monkeypatch)

    fake_client = _ConfigCapturingClient("plain response")
    monkeypatch.setattr(gemini_provider, "_get_client", lambda: fake_client)

    gemini_provider.GeminiProvider().generate("some prompt")

    sent_config = fake_client.models.seen_configs[0]
    expected_timeout_ms = int(gemini_provider.GEMINI_REQUEST_TIMEOUT_SECONDS * 1000)

    assert sent_config.http_options is not None
    assert sent_config.http_options.timeout == expected_timeout_ms


def test_call_gemini_applies_configured_timeout_with_json_schema(monkeypatch):
    _patch_no_sleep(monkeypatch)

    fake_client = _ConfigCapturingClient('{"ok": true}')
    monkeypatch.setattr(gemini_provider, "_get_client", lambda: fake_client)

    gemini_provider.GeminiProvider().generate(
        "some prompt", json_schema={"type": "object"}
    )

    sent_config = fake_client.models.seen_configs[0]
    expected_timeout_ms = int(gemini_provider.GEMINI_REQUEST_TIMEOUT_SECONDS * 1000)

    assert sent_config.http_options is not None
    assert sent_config.http_options.timeout == expected_timeout_ms
