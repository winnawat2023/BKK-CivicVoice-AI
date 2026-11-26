from civic import config
from civic.config import Settings


def test_defaults_are_safe_for_a_slow_llm():
    s = Settings()
    assert s.vllm_model == "typhoon-8b"
    assert s.rag_use_llm is False  # curated answers are instant; LLM paraphrase is opt-in
    assert s.llm_timeout_s >= 6


def test_from_env_overrides_and_bad_values_fall_back(monkeypatch):
    monkeypatch.setattr(config, "load_env_file", lambda: None)
    monkeypatch.setenv("VLLM_URL", "http://example:9/v1/chat/completions")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("LLM_TIMEOUT_S", "not-a-number")
    monkeypatch.setenv("RAG_USE_LLM", "yes")
    monkeypatch.setenv("CORS_ORIGINS", "http://a, http://b")
    s = Settings.from_env()
    assert s.vllm_url.startswith("http://example:9")
    assert s.llm_enabled is False
    assert s.llm_timeout_s == Settings().llm_timeout_s
    assert s.rag_use_llm is True
    assert s.cors_origins == ("http://a", "http://b")
