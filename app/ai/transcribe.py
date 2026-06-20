"""Voice-note transcription via Whisper.

Replaces the original Google SpeechRecognition + pydub + soundfile stack (and an
OGG->WAV conversion step) with a single Whisper call. WhatsApp voice notes are
OGG/Opus, which Whisper accepts directly.
"""
from __future__ import annotations

import io

from config import Config
from .client import get_client


def transcribe_audio(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Transcribe raw audio bytes to text."""
    client = get_client()
    buffer = io.BytesIO(audio_bytes)
    buffer.name = filename  # the SDK uses the name to infer the format
    result = client.audio.transcriptions.create(
        model=Config.TRANSCRIBE_MODEL,
        file=buffer,
    )
    return (getattr(result, "text", "") or "").strip()
