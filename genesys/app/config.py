"""Application configuration loaded from environment variables / `.env`."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_INSTRUCTIONS = (
    "You are a friendly and concise phone assistant. "
    "Speak and respond only in Thai or English. "
    "Never use any other language. "
    "If the caller speaks another language, politely reply in Thai or English "
    "and explain that only Thai and English are supported. "
    "Keep answers short and natural, as if speaking on a real phone call. "
    "Ask a clarifying question when the request is ambiguous."
)


class Settings(BaseSettings):
    """Runtime settings.

    Every field declares its environment variable name through
    ``validation_alias`` so the variable names stay stable even if the Python
    attribute names are refactored.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # -- HTTP / WSS server ---------------------------------------------------
    host: str = Field("0.0.0.0", validation_alias="HOST")
    port: int = Field(8080, validation_alias="PORT")
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    audiohook_path: str = Field("/api/v1/audiohook/ws", validation_alias="AUDIOHOOK_PATH")
    # Optional TLS. For Genesys Cloud production this must be a public CA cert
    # (or terminate TLS at a public load balancer/reverse proxy instead).
    ssl_certfile: str = Field("", validation_alias="SSL_CERTFILE")
    ssl_keyfile: str = Field("", validation_alias="SSL_KEYFILE")
    ssl_ca_certs: str = Field("", validation_alias="SSL_CA_CERTS")

    # -- Genesys client authentication --------------------------------------
    verify_signature: bool = Field(True, validation_alias="AUDIOHOOK_VERIFY_SIGNATURE")
    allow_unsigned: bool = Field(False, validation_alias="AUDIOHOOK_ALLOW_UNSIGNED")
    genesys_api_key: str = Field("", validation_alias="GENESYS_API_KEY")
    genesys_client_secret: str = Field("", validation_alias="GENESYS_CLIENT_SECRET")
    max_signature_age: int = Field(30, validation_alias="AUDIOHOOK_MAX_SIGNATURE_AGE")

    # -- AI provider selection ----------------------------------------------
    # "openai" => OpenAI Realtime, "gemini" => Google Gemini Live API
    ai_provider: str = Field("openai", validation_alias="AI_PROVIDER")

    # -- OpenAI Realtime ----------------------------------------------------
    openai_api_key: str = Field("", validation_alias="OPENAI_API_KEY")
    openai_realtime_url: str = Field(
        "wss://api.openai.com/v1/realtime", validation_alias="OPENAI_REALTIME_URL"
    )
    openai_model: str = Field("gpt-realtime", validation_alias="OPENAI_REALTIME_MODEL")
    openai_voice: str = Field("alloy", validation_alias="OPENAI_VOICE")
    # "pcmu" => G.711 mu-law 8kHz passthrough, "pcm" => PCM16 24kHz + resample
    openai_audio_format: str = Field("pcmu", validation_alias="OPENAI_AUDIO_FORMAT")
    openai_transcription_model: str = Field(
        "gpt-4o-mini-transcribe", validation_alias="OPENAI_TRANSCRIPTION_MODEL"
    )
    openai_instructions: str = Field(
        DEFAULT_INSTRUCTIONS, validation_alias="OPENAI_INSTRUCTIONS"
    )
    openai_connect_timeout: float = Field(
        4.0, validation_alias="OPENAI_CONNECT_TIMEOUT"
    )

    # -- Gemini Live API ----------------------------------------------------
    gemini_api_key: str = Field("", validation_alias="GEMINI_API_KEY")
    gemini_live_url: str = Field(
        "wss://generativelanguage.googleapis.com/ws/"
        "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent",
        validation_alias="GEMINI_LIVE_URL",
    )
    gemini_model: str = Field("gemini-3.8-live", validation_alias="GEMINI_MODEL")
    gemini_voice: str = Field("Kore", validation_alias="GEMINI_VOICE")
    # Gemini Live always speaks 16-bit PCM: input 16 kHz, output 24 kHz.
    gemini_input_sample_rate: int = Field(
        16000, validation_alias="GEMINI_INPUT_SAMPLE_RATE"
    )
    gemini_output_sample_rate: int = Field(
        24000, validation_alias="GEMINI_OUTPUT_SAMPLE_RATE"
    )
    gemini_instructions: str = Field(
        DEFAULT_INSTRUCTIONS, validation_alias="GEMINI_INSTRUCTIONS"
    )
    gemini_connect_timeout: float = Field(
        8.0, validation_alias="GEMINI_CONNECT_TIMEOUT"
    )
    gemini_enable_transcription: bool = Field(
        True, validation_alias="GEMINI_ENABLE_TRANSCRIPTION"
    )
    # Session resumption lets a call survive Gemini's ~15 minute audio limit.
    gemini_session_resumption: bool = Field(
        True, validation_alias="GEMINI_SESSION_RESUMPTION"
    )
    gemini_reconnect_attempts: int = Field(
        2, validation_alias="GEMINI_RECONNECT_ATTEMPTS"
    )
    gemini_context_window_compression: bool = Field(
        True, validation_alias="GEMINI_CONTEXT_WINDOW_COMPRESSION"
    )
    # Server-side VAD tuning (milliseconds).
    gemini_vad_prefix_ms: int = Field(300, validation_alias="GEMINI_VAD_PREFIX_MS")
    gemini_vad_silence_ms: int = Field(600, validation_alias="GEMINI_VAD_SILENCE_MS")
    # Text used to trigger the opening line. Empty => BOT_GREETING_INSTRUCTIONS.
    gemini_greeting_prompt: str = Field(
        "", validation_alias="GEMINI_GREETING_PROMPT"
    )

    # -- Typhoon / vLLM (self-hosted OpenAI-compatible chat) ---------------
    # Used when AI_PROVIDER=typhoon. LLM is called via OpenAI-compatible
    # /v1/chat/completions. STT/TTS are used to convert between Genesys audio
    # and text because chat-completions is text-only.
    typhoon_base_url: str = Field(
        "http://127.0.0.1:8001/v1", validation_alias="TYPHOON_BASE_URL"
    )
    typhoon_api_key: str = Field("", validation_alias="TYPHOON_API_KEY")
    typhoon_model: str = Field("typhoon-8b", validation_alias="TYPHOON_MODEL")
    typhoon_instructions: str = Field(
        DEFAULT_INSTRUCTIONS, validation_alias="TYPHOON_INSTRUCTIONS"
    )
    typhoon_connect_timeout: float = Field(
        10.0, validation_alias="TYPHOON_CONNECT_TIMEOUT"
    )
    typhoon_max_tokens: int = Field(200, validation_alias="TYPHOON_MAX_TOKENS")
    typhoon_temperature: float = Field(
        0.3, validation_alias="TYPHOON_TEMPERATURE"
    )
    typhoon_voicebot_url: str = Field(
        "", validation_alias="TYPHOON_VOICEBOT_URL"
    )

    # STT: OpenAI-compatible /v1/audio/transcriptions (e.g. faster-whisper-server)
    typhoon_stt_base_url: str = Field(
        "http://127.0.0.1:5001/v1", validation_alias="TYPHOON_STT_BASE_URL"
    )
    typhoon_stt_api_key: str = Field("", validation_alias="TYPHOON_STT_API_KEY")
    typhoon_stt_model: str = Field(
        "large-v3-turbo", validation_alias="TYPHOON_STT_MODEL"
    )
    typhoon_stt_language: str = Field("", validation_alias="TYPHOON_STT_LANGUAGE")

    # TTS: "edge_tts" (Microsoft edge-tts, like BKK-CivicVoice-AI) or "openai"
    # for an OpenAI-compatible /v1/audio/speech endpoint.
    typhoon_tts_provider: str = Field(
        "edge_tts", validation_alias="TYPHOON_TTS_PROVIDER"
    )
    typhoon_tts_base_url: str = Field(
        "http://127.0.0.1:8002/v1", validation_alias="TYPHOON_TTS_BASE_URL"
    )
    typhoon_tts_api_key: str = Field("", validation_alias="TYPHOON_TTS_API_KEY")
    typhoon_tts_model: str = Field("tts-1", validation_alias="TYPHOON_TTS_MODEL")
    typhoon_tts_voice: str = Field(
        "th-TH-PremwadeeNeural", validation_alias="TYPHOON_TTS_VOICE"
    )
    typhoon_tts_speed: float = Field(1.0, validation_alias="TYPHOON_TTS_SPEED")

    # Simple VAD for cascade turn-taking (PCMU 8kHz).
    typhoon_vad_silence_ms: int = Field(
        700, validation_alias="TYPHOON_VAD_SILENCE_MS"
    )
    typhoon_vad_energy_threshold: int = Field(
        180, validation_alias="TYPHOON_VAD_ENERGY_THRESHOLD"
    )
    typhoon_max_utterance_s: float = Field(
        15.0, validation_alias="TYPHOON_MAX_UTTERANCE_S"
    )

    # -- Bot behaviour ------------------------------------------------------
    bot_greeting: bool = Field(True, validation_alias="BOT_GREETING")
    greeting_instructions: str = Field(
        "Greet the caller warmly in one short sentence and ask how you can help.",
        validation_alias="BOT_GREETING_INSTRUCTIONS",
    )

    # -- Transcript webhook -------------------------------------------------
    transcript_webhook_url: str = Field("", validation_alias="TRANSCRIPT_WEBHOOK_URL")
    transcript_webhook_timeout: float = Field(
        5.0, validation_alias="TRANSCRIPT_WEBHOOK_TIMEOUT"
    )
    transcript_webhook_bearer_token: str = Field(
        "", validation_alias="TRANSCRIPT_WEBHOOK_BEARER_TOKEN"
    )
    transcript_fallback_dir: str = Field(
        "", validation_alias="TRANSCRIPT_FALLBACK_DIR"
    )

    # -- Outbound audio pacing ---------------------------------------------
    # Genesys: "do not send audio more often than every 200ms" and "no more
    # than 64,000 bytes per message".
    server_audio_chunk_ms: int = Field(
        200, validation_alias="GENESYS_SERVER_AUDIO_CHUNK_MS"
    )
    max_binary_frame_bytes: int = Field(
        64000, validation_alias="GENESYS_MAX_BINARY_FRAME_BYTES"
    )

    @property
    def provider(self) -> str:
        """Normalised AI provider name: ``openai``, ``gemini``, or ``typhoon``."""

        name = (self.ai_provider or "").strip().lower()
        if name in ("gemini", "google", "google-gemini"):
            return "gemini"
        if name in ("typhoon", "vllm", "typhoon-vllm"):
            return "typhoon"
        return "openai"

    @property
    def openai_ready(self) -> bool:
        """True when an OpenAI API key is configured."""
        return bool(self.openai_api_key.strip())

    @property
    def gemini_ready(self) -> bool:
        """True when a Gemini API key is configured."""
        return bool(self.gemini_api_key.strip())

    @property
    def typhoon_ready(self) -> bool:
        """True when the Typhoon/vLLM endpoint is configured."""

        return bool(self.typhoon_base_url.strip())

    @property
    def ai_ready(self) -> bool:
        """True when the selected provider has credentials configured."""

        if self.provider == "gemini":
            return self.gemini_ready
        if self.provider == "typhoon":
            return self.typhoon_ready
        return self.openai_ready

    @property
    def normalized_audio_format(self) -> str:
        fmt = (self.openai_audio_format or "").strip().lower()
        return fmt if fmt in ("pcmu", "pcm") else "pcmu"

    @property
    def ssl_enabled(self) -> bool:
        return bool(self.ssl_certfile.strip() and self.ssl_keyfile.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
