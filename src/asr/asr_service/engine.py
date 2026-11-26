"""Faster-Whisper wrapper: lazy model loading, device auto-detection, TH/EN language handling."""

from __future__ import annotations

import io
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from .config import Settings

logger = logging.getLogger("bkk-asr")

# Whisper's own "this is silence" heuristic: a segment that is probably not speech AND decoded with low confidence.
NO_SPEECH_PROB = 0.8
LOW_LOGPROB = -1.0
PROMPT_LANGUAGE = "th"  # language of ASR_INITIAL_PROMPT


class ASRError(RuntimeError):
    """Transcription failed. ``status`` is the HTTP status the API reports for it."""

    status = 500


class ModelLoadError(ASRError):
    """The Faster-Whisper model could not be loaded (missing download, no GPU memory, bad path...)."""

    status = 503


class AudioDecodeError(ASRError):
    """The uploaded bytes are not audio that PyAV/ffmpeg can decode."""

    status = 422


@dataclass
class Transcript:
    text: str = ""
    language: str = ""
    language_probability: float = 0.0
    duration: float = 0.0
    segments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "language_probability": round(self.language_probability, 4),
            "duration": round(self.duration, 3),
            "segments": self.segments,
        }


def _resolve_device(device: str) -> str:
    if device in ("cuda", "cpu"):
        return device
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:  # ctranslate2 missing or broken CUDA runtime -> CPU still works
        return "cpu"


def _resolve_compute_type(compute_type: str, device: str) -> str:
    """Explicit setting wins. Auto picks the fastest type this device's CTranslate2 build really supports:
    e.g. GTX 1050 (Pascal) has no float16 kernels, so it gets int8_float32 instead of failing to load."""
    if compute_type != "auto":
        return compute_type
    if device != "cuda":
        return "int8"
    try:
        import ctranslate2

        supported = set(ctranslate2.get_supported_compute_types("cuda"))
    except Exception:
        supported = set()
    for choice in ("float16", "int8_float16", "int8_float32", "int8"):
        if choice in supported:
            return choice
    return "int8"


def _default_model_factory(settings: Settings, device: str, compute_type: str) -> Any:
    from faster_whisper import WhisperModel

    kwargs: dict[str, Any] = {"device": device, "compute_type": compute_type, "cpu_threads": settings.cpu_threads}
    if settings.download_root:
        kwargs["download_root"] = settings.download_root
    return WhisperModel(settings.model, **kwargs)


class WhisperEngine:
    """Owns one Faster-Whisper model. ``transcribe`` is blocking: call it from a worker thread."""

    def __init__(
        self,
        settings: Settings,
        model_factory: Callable[[Settings, str, str], Any] | None = None,
    ) -> None:
        self.settings = settings
        self._factory = model_factory or _default_model_factory
        self._model: Any = None
        self._lock = threading.Lock()
        self.device = ""
        self.compute_type = ""

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            device = _resolve_device(self.settings.device)
            compute_type = _resolve_compute_type(self.settings.compute_type, device)
            logger.info("Loading Faster-Whisper %r on %s (%s)...", self.settings.model, device, compute_type)
            try:
                self._model = self._factory(self.settings, device, compute_type)
            except Exception as exc:
                raise ModelLoadError(f"cannot load model {self.settings.model!r}: {exc}") from exc
            self.device, self.compute_type = device, compute_type
            logger.info("Model ready")

    # ------------------------------------------------------------------ decode
    def _prompt_for(self, language: str | None) -> str | None:
        """The civic-vocabulary hint is Thai text, so it is only used when decoding Thai. On English audio it made
        large-v3-turbo about 3x slower and, in one auto-detect run, produced multilingual gibberish."""
        return (self.settings.initial_prompt or None) if language == PROMPT_LANGUAGE else None

    def _run(self, audio: Any, language: str | None, prompt: str | None) -> tuple[Any, Any]:
        s = self.settings
        return self._model.transcribe(
            audio,
            language=language,
            beam_size=s.beam_size,
            vad_filter=s.vad_filter,
            initial_prompt=prompt,
            condition_on_previous_text=False,  # stops a wrong word from snowballing across segments
        )

    @staticmethod
    def _open(audio: bytes | np.ndarray | str) -> Any:
        return io.BytesIO(audio) if isinstance(audio, (bytes, bytearray)) else audio

    def transcribe(self, audio: bytes | np.ndarray | str, language: str | None = None) -> Transcript:
        """Transcribe encoded audio bytes (wav/mp3/ogg/...), a file path, or mono float32 16 kHz samples.

        ``language``: ``None``/"auto" detects the language but only accepts the allowed ones (default Thai and
        English); anything else is decoded again as the fallback language, because Whisper often mislabels
        short Thai phone speech as another language.
        """
        self.load()
        requested = (language or self.settings.language or "auto").strip().lower()
        forced = None if requested == "auto" else requested
        try:
            if forced is not None:
                segments, info = self._run(self._open(audio), forced, self._prompt_for(forced))
            else:
                # Detection happens inside transcribe(), before any decoding, so the first call is cheap to discard.
                segments, info = self._run(self._open(audio), None, None)
                chosen = info.language
                if chosen not in self.settings.allowed_languages:
                    chosen = self.settings.fallback_language
                    logger.info(
                        "Detected %r (p=%.2f) is not allowed; decoding as %r",
                        info.language, info.language_probability, chosen,
                    )
                prompt = self._prompt_for(chosen)
                if chosen != info.language or prompt:
                    segments, info = self._run(self._open(audio), chosen, prompt)
            items = list(segments)  # the generator does the real decoding here
        except ASRError:
            raise
        except Exception as exc:
            if type(exc).__module__.split(".")[0] == "av":  # PyAV could not open/decode the bytes
                raise AudioDecodeError(f"cannot decode audio: {exc}") from exc
            raise ASRError(f"transcription failed: {exc}") from exc

        kept = [
            {
                "start": round(float(seg.start), 3),
                "end": round(float(seg.end), 3),
                "text": seg.text.strip(),
            }
            for seg in items
            if seg.text.strip() and not self._is_silence(seg)
        ]
        text = re.sub(r"\s+", " ", "".join(seg.text for seg in items if self._keep(seg))).strip()
        return Transcript(
            text=text,
            language=str(info.language),
            language_probability=float(info.language_probability),
            duration=float(info.duration),
            segments=kept,
        )

    @staticmethod
    def _is_silence(seg: Any) -> bool:
        return (
            getattr(seg, "no_speech_prob", 0.0) > NO_SPEECH_PROB
            and getattr(seg, "avg_logprob", 0.0) < LOW_LOGPROB
        )

    def _keep(self, seg: Any) -> bool:
        return bool(seg.text.strip()) and not self._is_silence(seg)
