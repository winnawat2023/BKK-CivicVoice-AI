"""Remote engine: sends audio to an existing Thai ASR service over HTTP (Typhoon Audio / Whisper large-v3 on DGX 100).

It has the same interface as ``WhisperEngine`` (``load``, ``loaded``, ``transcribe``), so the REST endpoint, the live
stream segmenter and the forwarding to the CivicVoice API are unchanged.

The remote service is Thai-only. In testing its ``language`` field made no difference on English audio (the clip came
back as repeated Thai tokens), so English is refused with HTTP 422 instead of being passed through as garbage.
"""

from __future__ import annotations

import io
import os
import re
import threading
import wave
from typing import Any

import httpx
import numpy as np

from .audio import WHISPER_RATE
from .config import Settings
from .engine import ASRError, ModelLoadError, Transcript

REMOTE_LANGUAGE = "th"  # the only language the remote service decodes
ACCEPTED_REQUESTS = ("auto", REMOTE_LANGUAGE)  # "auto" is treated as Thai because the remote cannot detect languages


class UnsupportedLanguageError(ASRError):
    """The request asks for a language the remote engine cannot decode."""

    status = 422


class RemoteUnavailableError(ASRError):
    """The remote ASR service could not be reached or timed out."""

    status = 503


class RemoteFailedError(ASRError):
    """The remote ASR service answered, but not with a usable transcript."""

    status = 502


def _seconds(value: Any) -> float:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return 0.0


def _wav_bytes(samples: np.ndarray, rate: int = WHISPER_RATE) -> bytes:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buf.getvalue()


class RemoteEngine:
    """Transcribes by calling ``POST /transcribe/file`` on the remote service. ``transcribe`` is blocking."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self._client = httpx.Client(
            base_url=settings.remote_url,
            timeout=settings.remote_timeout_s,
            transport=transport,
        )
        self._lock = threading.Lock()
        self._ready = False
        self.device = ""
        self.compute_type = ""

    @property
    def loaded(self) -> bool:
        return self._ready

    def load(self) -> None:
        """Check the remote service is up and has its model loaded. Cheap to call again; retried until it succeeds."""
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            try:
                response = self._client.get("/healthz")
                response.raise_for_status()
                body = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise ModelLoadError(f"remote ASR not reachable at {self.settings.remote_url}: {exc}") from exc
            if body.get("status") != "ok" or not body.get("model_loaded"):
                raise ModelLoadError(f"remote ASR is not ready: {body}")
            self.device = str(body.get("device") or "remote")
            self.compute_type = "remote"
            self._ready = True

    def transcribe(self, audio: bytes | np.ndarray | str, language: str | None = None) -> Transcript:
        """Transcribe encoded audio bytes, a file path, or mono float32 16 kHz samples (as WhisperEngine does)."""
        requested = (language or self.settings.language or "auto").strip().lower()
        if requested not in ACCEPTED_REQUESTS:
            raise UnsupportedLanguageError(
                f"remote ASR decodes Thai only; language {requested!r} is not supported"
            )
        self.load()
        filename, data, mime = self._encode(audio)
        try:
            response = self._client.post(
                "/transcribe/file",
                data={"language": REMOTE_LANGUAGE},
                files={"file": (filename, data, mime)},
            )
        except httpx.HTTPError as exc:
            raise RemoteUnavailableError(f"remote ASR request failed: {exc}") from exc

        if response.status_code != 200:
            raise RemoteFailedError(f"remote ASR returned HTTP {response.status_code}: {response.text[:200]}")
        try:
            body = response.json()
        except ValueError as exc:
            raise RemoteFailedError("remote ASR returned a non-JSON body") from exc
        if body.get("status") != "success":
            raise RemoteFailedError(f"remote ASR reported status {body.get('status')!r}")

        text = re.sub(r"\s+", " ", str(body.get("text") or "")).strip()
        segments: list[dict[str, Any]] = []
        for chunk in body.get("chunks") or []:
            chunk_text = str(chunk.get("text") or "").strip()
            timestamp = chunk.get("timestamp") or [None, None]
            if chunk_text:
                segments.append({"start": _seconds(timestamp[0]), "end": _seconds(timestamp[1]), "text": chunk_text})
        return Transcript(
            text=text,
            language=REMOTE_LANGUAGE,
            language_probability=0.0,  # the remote service does not report a confidence
            duration=self._duration(audio, segments),
            segments=segments,
        )

    @staticmethod
    def _encode(audio: bytes | np.ndarray | str) -> tuple[str, bytes, str]:
        if isinstance(audio, np.ndarray):
            return "utterance.wav", _wav_bytes(audio), "audio/wav"
        if isinstance(audio, (bytes, bytearray)):
            # The remote sniffs the format from the content (an mp3 sent as "audio.bin" decodes fine), so the name is
            # only a label.
            return "audio.bin", bytes(audio), "application/octet-stream"
        with open(audio, "rb") as handle:
            return os.path.basename(str(audio)) or "audio.bin", handle.read(), "application/octet-stream"

    @staticmethod
    def _duration(audio: bytes | np.ndarray | str, segments: list[dict[str, Any]]) -> float:
        if isinstance(audio, np.ndarray):
            return round(audio.size / WHISPER_RATE, 3)
        return max((seg["end"] for seg in segments), default=0.0)

    def close(self) -> None:
        self._client.close()
