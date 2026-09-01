"""
Tests for app/services/voice_service.py.

No real network calls: requests.post is monkeypatched, mirroring the
pattern used for the Groq chat provider in tests/test_groq.py. Confirms
voice_service never imports the LLM abstraction (constraint: transcription
must not be coupled to LLM_PROVIDER) and handles missing audio, API
failures, empty transcripts, and unsupported audio gracefully.
"""

import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from services import voice_service  # noqa: E402


def test_voice_service_does_not_import_llm_package():
    # voice_service.py must stay independent of app/llm/ -- it should
    # never see LLM_PROVIDER or know a second provider exists.
    assert "llm" not in vars(voice_service)
    assert not hasattr(voice_service, "factory")
    assert not hasattr(voice_service, "gemini_provider")
    assert not hasattr(voice_service, "groq_provider")


# ---------------------------------------------------------------------
# Missing audio / missing API key
# ---------------------------------------------------------------------


def test_transcribe_audio_rejects_empty_bytes(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    with pytest.raises(voice_service.VoiceServiceError, match="No audio"):
        voice_service.transcribe_audio(b"")


def test_transcribe_audio_missing_api_key_raises_before_request(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    fake_post = _FakePost([])
    monkeypatch.setattr(voice_service.requests, "post", fake_post)

    with pytest.raises(voice_service.VoiceServiceError, match="GROQ_API_KEY"):
        voice_service.transcribe_audio(b"fake-wav-bytes")

    assert fake_post.call_count == 0


# ---------------------------------------------------------------------
# Fake requests.post plumbing
# ---------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (str(payload) if payload else "")

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


class _FakePost:
    def __init__(self, effects: list):
        self._effects = list(effects)
        self.call_count = 0
        self.seen_kwargs: list = []

    def __call__(self, url, *, headers, files, data, timeout):
        self.call_count += 1
        self.seen_kwargs.append(
            {
                "url": url,
                "headers": headers,
                "files": files,
                "data": data,
                "timeout": timeout,
            }
        )

        if not self._effects:
            raise AssertionError("No more fake effects queued")

        effect = self._effects.pop(0)

        if isinstance(effect, Exception):
            raise effect

        return effect


def _patch_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")


# ---------------------------------------------------------------------
# Successful transcription
# ---------------------------------------------------------------------


def test_transcribe_audio_success(monkeypatch):
    _patch_env(monkeypatch)

    fake_post = _FakePost(
        [_FakeResponse(200, {"text": "  How much revenue did we make?  "})]
    )
    monkeypatch.setattr(voice_service.requests, "post", fake_post)

    result = voice_service.transcribe_audio(b"fake-wav-bytes", filename="q.wav")

    assert result == "How much revenue did we make?"
    assert fake_post.call_count == 1

    sent = fake_post.seen_kwargs[0]
    assert sent["data"]["model"] == voice_service.GROQ_WHISPER_MODEL
    assert sent["files"]["file"][0] == "q.wav"
    assert sent["timeout"] == voice_service.GROQ_WHISPER_TIMEOUT_SECONDS


def test_transcribe_audio_uses_default_filename(monkeypatch):
    _patch_env(monkeypatch)

    fake_post = _FakePost([_FakeResponse(200, {"text": "hello"})])
    monkeypatch.setattr(voice_service.requests, "post", fake_post)

    voice_service.transcribe_audio(b"fake-wav-bytes")

    assert fake_post.seen_kwargs[0]["files"]["file"][0] == "recording.wav"


# ---------------------------------------------------------------------
# Empty transcript (silence)
# ---------------------------------------------------------------------


def test_transcribe_audio_empty_transcript_raises(monkeypatch):
    _patch_env(monkeypatch)

    fake_post = _FakePost([_FakeResponse(200, {"text": "   "})])
    monkeypatch.setattr(voice_service.requests, "post", fake_post)

    with pytest.raises(voice_service.VoiceServiceError, match="No speech"):
        voice_service.transcribe_audio(b"fake-wav-bytes")


def test_transcribe_audio_missing_text_field_raises(monkeypatch):
    _patch_env(monkeypatch)

    fake_post = _FakePost([_FakeResponse(200, {"unexpected": "shape"})])
    monkeypatch.setattr(voice_service.requests, "post", fake_post)

    with pytest.raises(voice_service.VoiceServiceError, match="unexpected response"):
        voice_service.transcribe_audio(b"fake-wav-bytes")


# ---------------------------------------------------------------------
# API / unsupported-audio failures
# ---------------------------------------------------------------------


def test_transcribe_audio_unsupported_format_raises(monkeypatch):
    _patch_env(monkeypatch)

    fake_post = _FakePost([_FakeResponse(400, text="invalid audio format")])
    monkeypatch.setattr(voice_service.requests, "post", fake_post)

    with pytest.raises(
        voice_service.VoiceServiceError, match="could not be transcribed"
    ):
        voice_service.transcribe_audio(b"not-really-audio")


def test_transcribe_audio_rate_limited_raises(monkeypatch):
    _patch_env(monkeypatch)

    fake_post = _FakePost([_FakeResponse(429, text="rate limited")])
    monkeypatch.setattr(voice_service.requests, "post", fake_post)

    with pytest.raises(voice_service.VoiceServiceError, match="rate limited"):
        voice_service.transcribe_audio(b"fake-wav-bytes")


def test_transcribe_audio_server_error_raises(monkeypatch):
    _patch_env(monkeypatch)

    fake_post = _FakePost([_FakeResponse(500, text="internal error")])
    monkeypatch.setattr(voice_service.requests, "post", fake_post)

    with pytest.raises(
        voice_service.VoiceServiceError, match="temporarily unavailable"
    ):
        voice_service.transcribe_audio(b"fake-wav-bytes")


def test_transcribe_audio_timeout_raises(monkeypatch):
    _patch_env(monkeypatch)

    def _raise_timeout(*args, **kwargs):
        raise voice_service.requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(voice_service.requests, "post", _raise_timeout)

    with pytest.raises(voice_service.VoiceServiceError, match="timed out"):
        voice_service.transcribe_audio(b"fake-wav-bytes")


def test_transcribe_audio_connection_error_raises(monkeypatch):
    _patch_env(monkeypatch)

    def _raise_connection_error(*args, **kwargs):
        raise voice_service.requests.exceptions.ConnectionError("no network")

    monkeypatch.setattr(voice_service.requests, "post", _raise_connection_error)

    with pytest.raises(voice_service.VoiceServiceError, match="could not be reached"):
        voice_service.transcribe_audio(b"fake-wav-bytes")


def test_transcribe_audio_never_raises_raw_requests_exception(monkeypatch):
    """
    The UI must only ever see VoiceServiceError, never a raw requests/API
    exception -- mirrors the same rule already enforced for LLMError.
    """
    _patch_env(monkeypatch)

    fake_post = _FakePost([_FakeResponse(500, text="internal error")])
    monkeypatch.setattr(voice_service.requests, "post", fake_post)

    try:
        voice_service.transcribe_audio(b"fake-wav-bytes")
    except voice_service.VoiceServiceError:
        pass
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail(f"Raw exception leaked instead of VoiceServiceError: {exc!r}")
