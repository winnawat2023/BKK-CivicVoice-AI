"""Runtime settings, read from environment variables (and an optional ``.env`` file).

Secrets (server passwords, API keys) never live in code: put them in ``src/backend/.env``,
which is git-ignored. See ``src/backend/.env.example`` for the supported variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]


def load_env_file() -> None:
    """Load ``src/backend/.env`` then ``./.env`` if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional at runtime
        return
    load_dotenv(_BACKEND_DIR / ".env")
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


@dataclass(frozen=True)
class Settings:
    # --- Thai LLM (vLLM, OpenAI-compatible API) ---
    vllm_url: str = "http://127.0.0.1:8001/v1/chat/completions"
    vllm_model: str = "typhoon-8b"
    vllm_api_key: str = ""
    llm_enabled: bool = True
    llm_timeout_s: float = 8.0  # classification budget before falling back to rules (vLLM ~13 tok/s measured)
    llm_json_mode: bool = False  # send response_format=json_object (needs vLLM support)

    # --- Civic RAG ---
    rag_use_llm: bool = False  # False = answer instantly from curated snippets; True = LLM paraphrase (needs fast vLLM)
    rag_timeout_s: float = 1.8  # NFR1: answer starts within 2 s
    rag_min_score: float = 0.22  # below this the bot says "no information"
    rag_top_k: int = 3

    # --- Ticket store / sessions ---
    db_path: str = str(_REPO_ROOT / "data" / "tickets.db")  # ":memory:" for tests
    session_ttl_s: int = 3600
    max_transcript_segments: int = 200

    # --- HTTP ---
    cors_origins: tuple[str, ...] = ("*",)

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        defaults = cls()
        origins = os.getenv("CORS_ORIGINS", "*")
        return cls(
            vllm_url=os.getenv("VLLM_URL", defaults.vllm_url),
            vllm_model=os.getenv("VLLM_MODEL", defaults.vllm_model),
            vllm_api_key=os.getenv("VLLM_API_KEY", defaults.vllm_api_key),
            llm_enabled=_env_bool("LLM_ENABLED", defaults.llm_enabled),
            llm_timeout_s=_env_float("LLM_TIMEOUT_S", defaults.llm_timeout_s),
            llm_json_mode=_env_bool("LLM_JSON_MODE", defaults.llm_json_mode),
            rag_use_llm=_env_bool("RAG_USE_LLM", defaults.rag_use_llm),
            rag_timeout_s=_env_float("RAG_TIMEOUT_S", defaults.rag_timeout_s),
            rag_min_score=_env_float("RAG_MIN_SCORE", defaults.rag_min_score),
            rag_top_k=_env_int("RAG_TOP_K", defaults.rag_top_k),
            db_path=os.getenv("DB_PATH", defaults.db_path),
            session_ttl_s=_env_int("SESSION_TTL_S", defaults.session_ttl_s),
            max_transcript_segments=_env_int(
                "MAX_TRANSCRIPT_SEGMENTS", defaults.max_transcript_segments
            ),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()) or ("*",),
        )
