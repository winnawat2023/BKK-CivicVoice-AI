"""Runtime settings, read from environment variables (and an optional ``.env`` file).

No secrets are needed by this service. See ``src/asr/.env.example`` for every supported variable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_ASR_DIR = Path(__file__).resolve().parents[1]


def load_env_file() -> None:
    """Load ``src/asr/.env`` then ``./.env`` if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional at runtime
        return
    load_dotenv(_ASR_DIR / ".env")
    load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return tuple(p.strip().lower() for p in raw.split(",") if p.strip())


DEFAULT_INITIAL_PROMPT = (
    "สายด่วน กทม. 1555 แจ้งเหตุ ท่อระบายน้ำ ทางเท้า ไฟฟ้าสาธารณะ สำนักงานเขต ซอยสุขุมวิท"
)


@dataclass(frozen=True)
class Settings:
    # --- which engine transcribes ---
    engine: str = "local"  # local = Faster-Whisper in this process | remote = existing Thai ASR service over HTTP
    remote_url: str = "http://192.168.200.100:5001"  # used when engine=remote (DGX 100 Thai ASR service)
    remote_timeout_s: float = 30.0

    # --- Faster-Whisper model (engine=local) ---
    model: str = "large-v3-turbo"  # model alias, Hugging Face repo id, or a local CTranslate2 directory
    device: str = "auto"  # auto | cuda | cpu
    compute_type: str = "auto"  # auto -> float16 on cuda, int8 on cpu; or any CTranslate2 type
    cpu_threads: int = 0  # 0 = library default
    download_root: str = ""  # model cache directory ("" = Hugging Face default)
    preload: bool = False  # load the model at startup instead of on the first request

    # --- decoding ---
    language: str = "auto"  # th | en | ... | auto (detect, restricted to ``allowed_languages``)
    allowed_languages: tuple[str, ...] = ("th", "en")
    fallback_language: str = "th"  # used when auto-detect picks a language outside ``allowed_languages``
    beam_size: int = 5
    vad_filter: bool = True  # drop silence before decoding (also stops "ghost" text on quiet audio)
    initial_prompt: str = DEFAULT_INITIAL_PROMPT  # biases spelling toward civic vocabulary ("" = off)
    max_concurrency: int = 1  # simultaneous transcriptions on this process

    # --- upload ---
    max_upload_mb: int = 25

    # --- live streaming (WebSocket) ---
    energy_threshold: float = 0.012  # RMS (0..1) above which a 30 ms frame counts as speech
    endpoint_silence_ms: int = 700  # silence that ends an utterance
    partial_interval_ms: int = 1500  # emit a partial transcript this often while the caller speaks
    min_speech_ms: int = 250  # shorter bursts are treated as noise
    max_utterance_s: float = 20.0  # force a final transcript after this much continuous speech

    # --- hand-off to the CivicVoice API ---
    backend_url: str = "http://127.0.0.1:8000"
    backend_timeout_s: float = 5.0
    forward_default: bool = True  # forward when an interaction_id is supplied

    # --- HTTP ---
    cors_origins: tuple[str, ...] = ("*",)

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        d = cls()
        origins = os.getenv("CORS_ORIGINS", "*")
        return cls(
            engine=os.getenv("ASR_ENGINE", d.engine).strip().lower(),
            remote_url=os.getenv("ASR_REMOTE_URL", d.remote_url).rstrip("/"),
            remote_timeout_s=_env_float("ASR_REMOTE_TIMEOUT_S", d.remote_timeout_s),
            model=os.getenv("ASR_MODEL", d.model),
            device=os.getenv("ASR_DEVICE", d.device).strip().lower(),
            compute_type=os.getenv("ASR_COMPUTE_TYPE", d.compute_type).strip().lower(),
            cpu_threads=_env_int("ASR_CPU_THREADS", d.cpu_threads),
            download_root=os.getenv("ASR_DOWNLOAD_ROOT", d.download_root),
            preload=_env_bool("ASR_PRELOAD", d.preload),
            language=os.getenv("ASR_LANGUAGE", d.language).strip().lower() or "auto",
            allowed_languages=_env_list("ASR_ALLOWED_LANGUAGES", d.allowed_languages),
            fallback_language=os.getenv("ASR_FALLBACK_LANGUAGE", d.fallback_language).strip().lower(),
            beam_size=_env_int("ASR_BEAM_SIZE", d.beam_size),
            vad_filter=_env_bool("ASR_VAD_FILTER", d.vad_filter),
            initial_prompt=os.getenv("ASR_INITIAL_PROMPT", d.initial_prompt),
            max_concurrency=max(1, _env_int("ASR_MAX_CONCURRENCY", d.max_concurrency)),
            max_upload_mb=_env_int("ASR_MAX_UPLOAD_MB", d.max_upload_mb),
            energy_threshold=_env_float("ASR_ENERGY_THRESHOLD", d.energy_threshold),
            endpoint_silence_ms=_env_int("ASR_ENDPOINT_SILENCE_MS", d.endpoint_silence_ms),
            partial_interval_ms=_env_int("ASR_PARTIAL_INTERVAL_MS", d.partial_interval_ms),
            min_speech_ms=_env_int("ASR_MIN_SPEECH_MS", d.min_speech_ms),
            max_utterance_s=_env_float("ASR_MAX_UTTERANCE_S", d.max_utterance_s),
            backend_url=os.getenv("BACKEND_URL", d.backend_url).rstrip("/"),
            backend_timeout_s=_env_float("BACKEND_TIMEOUT_S", d.backend_timeout_s),
            forward_default=_env_bool("FORWARD_DEFAULT", d.forward_default),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()) or ("*",),
        )
