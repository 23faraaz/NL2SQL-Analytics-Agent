"""
Tests for app/llm/groq_provider.py.

No real network calls are made -- requests.post is monkeypatched with a
fake Response-shaped object, mirroring the pattern used for Gemini in
tests/test_llm.py.
"""

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import llm  # noqa: E402
from llm import groq_provider  # noqa: E402


UNDERSTANDING_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "entities": {"type": "array", "items": {"type": "string"}},
        "time_filter": {"type": "string", "nullable": True},
        "aggregation": {"type": "string", "nullable": True},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "ambiguity": {"type": "boolean"},
        "sql": {"type": "string"},
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

VALID_UNDERSTANDING_JSON = (
    '{"intent": "count orders", "entities": ["orders"], '
    '"time_filter": null, "aggregation": "count", '
    '"assumptions": [], "ambiguity": false, '
    '"sql": "SELECT COUNT(*) FROM commerce.orders"}'
)


# ---------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------


def test_validate_config_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(groq_provider, "MODEL", "openai/gpt-oss-20b")

    with pytest.raises(llm.LLMError, match="GROQ_API_KEY"):
        groq_provider.validate_config()


def test_validate_config_missing_model_raises(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(groq_provider, "MODEL", None)

    with pytest.raises(llm.LLMError, match="GROQ_MODEL"):
        groq_provider.validate_config()


def test_validate_config_succeeds_with_both_set(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(groq_provider, "MODEL", "openai/gpt-oss-20b")

    groq_provider.validate_config()  # must not raise


# ---------------------------------------------------------------------
# Schema translation
# ---------------------------------------------------------------------


def test_translate_schema_converts_nullable_to_type_union():
    translated = groq_provider._translate_schema_for_strict_mode(
        UNDERSTANDING_SCHEMA
    )

    assert translated["properties"]["time_filter"]["type"] == ["string", "null"]
    assert "nullable" not in translated["properties"]["time_filter"]


def test_translate_schema_sets_additional_properties_false():
    translated = groq_provider._translate_schema_for_strict_mode(
        UNDERSTANDING_SCHEMA
    )

    assert translated["additionalProperties"] is False


def test_translate_schema_requires_every_property():
    translated = groq_provider._translate_schema_for_strict_mode(
        UNDERSTANDING_SCHEMA
    )

    assert set(translated["required"]) == set(translated["properties"].keys())


# ---------------------------------------------------------------------
# GroqProvider.generate() -- fake requests.post plumbing
# ---------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code, content=None, headers=None, text=""):
        self.status_code = status_code
        self._content = content
        self.headers = headers or {}
        self.text = text or (content or "")

    def json(self):
        if self._content is None:
            raise ValueError("no JSON body")

        return {
            "choices": [
                {"message": {"content": self._content}},
            ]
        }


def _ok_response(content: str) -> _FakeResponse:
    return _FakeResponse(200, content=content)


def _rate_limited_response(retry_after: str | None) -> _FakeResponse:
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    return _FakeResponse(429, headers=headers, text="rate limited")


def _server_error_response() -> _FakeResponse:
    return _FakeResponse(500, text="internal error")


def _client_error_response(status_code: int) -> _FakeResponse:
    return _FakeResponse(status_code, text="bad request")


class _FakePost:
    def __init__(self, effects: list):
        self._effects = list(effects)
        self.call_count = 0
        self.seen_kwargs: list = []

    def __call__(self, url, *, headers, json, timeout):
        self.call_count += 1
        self.seen_kwargs.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )

        if not self._effects:
            raise AssertionError("No more fake effects queued")

        effect = self._effects.pop(0)

        if isinstance(effect, Exception):
            raise effect

        return effect


def _patch_no_sleep(monkeypatch):
    monkeypatch.setattr(groq_provider.time, "sleep", lambda seconds: None)


def _patch_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(groq_provider, "MODEL", "openai/gpt-oss-20b")


def test_generate_plain_text_success(monkeypatch):
    _patch_no_sleep(monkeypatch)
    _patch_env(monkeypatch)

    fake_post = _FakePost([_ok_response("plain answer")])
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    result = groq_provider.GroqProvider().generate("some prompt")

    assert result == "plain answer"
    assert fake_post.call_count == 1
    assert "response_format" not in fake_post.seen_kwargs[0]["json"]


def test_generate_structured_json_success(monkeypatch):
    _patch_no_sleep(monkeypatch)
    _patch_env(monkeypatch)

    fake_post = _FakePost([_ok_response(VALID_UNDERSTANDING_JSON)])
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    result = groq_provider.GroqProvider().generate(
        "some prompt", json_schema=UNDERSTANDING_SCHEMA
    )

    assert result == VALID_UNDERSTANDING_JSON
    sent_body = fake_post.seen_kwargs[0]["json"]
    assert sent_body["response_format"]["type"] == "json_schema"
    assert sent_body["response_format"]["json_schema"]["strict"] is True


def test_generate_malformed_json_raises_llm_error(monkeypatch):
    _patch_no_sleep(monkeypatch)
    _patch_env(monkeypatch)

    fake_post = _FakePost([_ok_response("not valid json {{{")])
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    with pytest.raises(llm.LLMError, match="malformed JSON"):
        groq_provider.GroqProvider().generate(
            "some prompt", json_schema=UNDERSTANDING_SCHEMA
        )


def test_generate_structurally_invalid_json_raises_llm_error(monkeypatch):
    _patch_no_sleep(monkeypatch)
    _patch_env(monkeypatch)

    # Valid JSON, but missing required fields and wrong types.
    invalid_json = '{"intent": "count orders", "entities": "not-an-array"}'
    fake_post = _FakePost([_ok_response(invalid_json)])
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    with pytest.raises(llm.LLMError, match="did not match the expected schema"):
        groq_provider.GroqProvider().generate(
            "some prompt", json_schema=UNDERSTANDING_SCHEMA
        )


def test_generate_rate_limit_retries_then_succeeds(monkeypatch):
    _patch_no_sleep(monkeypatch)
    _patch_env(monkeypatch)

    fake_post = _FakePost(
        [_rate_limited_response("0.1"), _ok_response("final answer")]
    )
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    result = groq_provider.GroqProvider().generate("some prompt")

    assert result == "final answer"
    assert fake_post.call_count == 2


def test_generate_rate_limit_bounded_then_raises(monkeypatch):
    _patch_no_sleep(monkeypatch)
    _patch_env(monkeypatch)

    fake_post = _FakePost(
        [
            _rate_limited_response(None)
            for _ in range(groq_provider.GROQ_RATE_LIMIT_MAX_ATTEMPTS)
        ]
    )
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    with pytest.raises(llm.LLMError, match="rate limit or quota exceeded"):
        groq_provider.GroqProvider().generate("some prompt")

    assert fake_post.call_count == groq_provider.GROQ_RATE_LIMIT_MAX_ATTEMPTS


def test_generate_rate_limit_fails_fast_when_retry_after_exceeds_cap(monkeypatch):
    _patch_no_sleep(monkeypatch)
    _patch_env(monkeypatch)

    huge_delay = str(groq_provider.GROQ_RATE_LIMIT_MAX_DELAY_SECONDS + 60)
    fake_post = _FakePost([_rate_limited_response(huge_delay)])
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    with pytest.raises(llm.LLMError):
        groq_provider.GroqProvider().generate("some prompt")

    assert fake_post.call_count == 1


def test_generate_non_429_client_error_fails_immediately(monkeypatch):
    _patch_no_sleep(monkeypatch)
    _patch_env(monkeypatch)

    fake_post = _FakePost([_client_error_response(404)])
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    with pytest.raises(llm.LLMError):
        groq_provider.GroqProvider().generate("some prompt")

    assert fake_post.call_count == 1


def test_generate_server_error_retries_then_raises(monkeypatch):
    _patch_no_sleep(monkeypatch)
    _patch_env(monkeypatch)

    fake_post = _FakePost(
        [_server_error_response() for _ in range(groq_provider.MAX_ATTEMPTS)]
    )
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    with pytest.raises(llm.LLMError, match="temporarily unavailable"):
        groq_provider.GroqProvider().generate("some prompt")

    assert fake_post.call_count == groq_provider.MAX_ATTEMPTS


def test_generate_applies_configured_timeout(monkeypatch):
    _patch_no_sleep(monkeypatch)
    _patch_env(monkeypatch)

    fake_post = _FakePost([_ok_response("plain answer")])
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    groq_provider.GroqProvider().generate("some prompt")

    assert (
        fake_post.seen_kwargs[0]["timeout"]
        == groq_provider.GROQ_REQUEST_TIMEOUT_SECONDS
    )


def test_generate_missing_api_key_raises_before_request(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(groq_provider, "MODEL", "openai/gpt-oss-20b")

    fake_post = _FakePost([])
    monkeypatch.setattr(groq_provider.requests, "post", fake_post)

    with pytest.raises(llm.LLMError, match="GROQ_API_KEY"):
        groq_provider.GroqProvider().generate("some prompt")

    assert fake_post.call_count == 0
