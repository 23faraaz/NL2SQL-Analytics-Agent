"""
Voice input: audio -> transcribed text, nothing more.

This module is deliberately independent of app/llm/ -- it does not import
it, does not check LLM_PROVIDER, and does not know that SQL generation
exists. It always transcribes via Groq Whisper directly, reusing
GROQ_API_KEY, regardless of which provider is configured for the text
pipeline. That is what keeps voice input working identically whether
LLM_PROVIDER=gemini or LLM_PROVIDER=groq: the transcribed text is handed
back as a plain string, and the caller (app/main.py) feeds it into the
existing understand_and_generate_sql() pipeline exactly as if the user
had typed it.

Groq's audio transcription endpoint is a separate REST surface from the
chat completions endpoint app/llm/groq_provider.py uses (multipart file
upload, not JSON) -- see console.groq.com/docs/speech-to-text -- so this
module makes its own request rather than reusing groq_provider.py.
"""

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

# whisper-large-v3-turbo is the faster of Groq's two Whisper models
# (~216x realtime vs ~189x, 12% vs 10.3% word-error-rate) -- the better
# default for short, interactive spoken questions, same latency-first
# reasoning as the GROQ_MODEL default for chat. Unlike GROQ_MODEL /
# GEMINI_MODEL, a default is provided here per the explicit requirement
# that this be configurable but not mandatory to set.
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

GROQ_WHISPER_TIMEOUT_SECONDS = float(
    os.getenv("GROQ_WHISPER_TIMEOUT_SECONDS", "30")
)


class VoiceServiceError(Exception):
    """Single exception type exposed by the voice service."""


def _get_api_key() -> str:
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise VoiceServiceError(
            "Voice input requires GROQ_API_KEY to be set, regardless of "
            "which LLM_PROVIDER is configured for text questions."
        )

    return api_key


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "recording.wav",
) -> str:
    """
    Transcribe recorded audio to plain text via Groq Whisper.

    Raises VoiceServiceError -- never a raw requests/API exception -- on
    missing audio, request failures, unsupported/corrupt audio, or an
    empty transcript (silence). The full technical detail is logged
    server-side; only a clean, generic message is meant to reach the UI.
    """

    if not audio_bytes:
        raise VoiceServiceError("No audio was recorded.")

    api_key = _get_api_key()

    headers = {"Authorization": f"Bearer {api_key}"}

    files = {
        "file": (filename, audio_bytes, "audio/wav"),
    }

    data = {
        "model": GROQ_WHISPER_MODEL,
        "response_format": "json",
    }

    try:
        response = requests.post(
            GROQ_TRANSCRIPTION_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=GROQ_WHISPER_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as error:
        logger.error("Groq transcription request timed out: %s", error)
        raise VoiceServiceError(
            "The transcription request timed out. Please try again."
        ) from error
    except requests.exceptions.RequestException as error:
        logger.error("Groq transcription request failed: %s", error)
        raise VoiceServiceError(
            "The transcription service could not be reached. Please try again."
        ) from error

    if response.status_code == 429:
        logger.error(
            "Groq transcription rate limited: %s", response.text[:500]
        )
        raise VoiceServiceError(
            "The transcription service is rate limited. Please try again shortly."
        )

    if response.status_code >= 500:
        logger.error(
            "Groq transcription server error (%d): %s",
            response.status_code,
            response.text[:500],
        )
        raise VoiceServiceError(
            "The transcription service is temporarily unavailable. "
            "Please try again shortly."
        )

    if response.status_code >= 400:
        logger.error(
            "Groq transcription client error (%d): %s",
            response.status_code,
            response.text[:500],
        )
        raise VoiceServiceError(
            "The recording could not be transcribed. It may be in an "
            "unsupported format or too long. Please try recording again."
        )

    try:
        payload: dict[str, Any] = response.json()
        text = payload["text"]
    except (ValueError, KeyError, TypeError) as error:
        logger.error("Unexpected Groq transcription response shape: %s", error)
        raise VoiceServiceError(
            "The transcription service returned an unexpected response."
        ) from error

    if not isinstance(text, str) or not text.strip():
        raise VoiceServiceError(
            "No speech was detected in the recording. Please try again."
        )

    transcript = text.strip()

    logger.info("Audio transcribed (%d chars)", len(transcript))

    return transcript
