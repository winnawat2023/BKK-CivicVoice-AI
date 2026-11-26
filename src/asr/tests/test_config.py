from asr_service.config import Settings


def test_defaults_match_the_documented_deployment():
    s = Settings()
    assert s.model == "large-v3-turbo" and s.device == "auto" and s.compute_type == "auto"
    assert s.language == "auto" and s.allowed_languages == ("th", "en") and s.fallback_language == "th"
    assert s.backend_url == "http://127.0.0.1:8000" and s.max_concurrency == 1


def test_from_env_reads_and_normalises_values(monkeypatch):
    monkeypatch.setattr("asr_service.config.load_env_file", lambda: None)
    for key, value in {
        "ASR_MODEL": "small",
        "ASR_DEVICE": " CPU ",
        "ASR_COMPUTE_TYPE": "INT8",
        "ASR_PRELOAD": "yes",
        "ASR_LANGUAGE": "TH",
        "ASR_ALLOWED_LANGUAGES": "th, EN ,ja",
        "ASR_VAD_FILTER": "off",
        "ASR_INITIAL_PROMPT": "",
        "ASR_MAX_CONCURRENCY": "0",
        "ASR_ENERGY_THRESHOLD": "0.03",
        "ASR_ENDPOINT_SILENCE_MS": "900",
        "BACKEND_URL": "http://api.local:8000/",
        "FORWARD_DEFAULT": "false",
        "CORS_ORIGINS": "http://a.test, http://b.test",
    }.items():
        monkeypatch.setenv(key, value)
    s = Settings.from_env()
    assert (s.model, s.device, s.compute_type, s.preload, s.language) == ("small", "cpu", "int8", True, "th")
    assert s.allowed_languages == ("th", "en", "ja")
    assert s.vad_filter is False and s.initial_prompt == ""
    assert s.max_concurrency == 1  # never below 1
    assert s.energy_threshold == 0.03 and s.endpoint_silence_ms == 900
    assert s.backend_url == "http://api.local:8000" and s.forward_default is False
    assert s.cors_origins == ("http://a.test", "http://b.test")


def test_invalid_numbers_fall_back_to_defaults(monkeypatch):
    monkeypatch.setattr("asr_service.config.load_env_file", lambda: None)
    monkeypatch.setenv("ASR_BEAM_SIZE", "many")
    monkeypatch.setenv("ASR_ENERGY_THRESHOLD", "loud")
    s = Settings.from_env()
    assert s.beam_size == Settings().beam_size and s.energy_threshold == Settings().energy_threshold
