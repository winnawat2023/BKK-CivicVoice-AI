"""WhisperEngine behaviour against a stub model (no download, no GPU)."""

from __future__ import annotations

import io
from types import SimpleNamespace

import numpy as np
import pytest

from asr_service.engine import (
    ASRError,
    AudioDecodeError,
    ModelLoadError,
    WhisperEngine,
    _resolve_compute_type,
    _resolve_device,
)

from .conftest import make_settings


def seg(text, start=0.0, end=1.0, no_speech_prob=0.0, avg_logprob=-0.2):
    return SimpleNamespace(text=text, start=start, end=end, no_speech_prob=no_speech_prob, avg_logprob=avg_logprob)


def info(language="th", probability=0.97, duration=3.0):
    return SimpleNamespace(language=language, language_probability=probability, duration=duration)


class StubModel:
    """Returns scripted (segments, info) pairs, one per ``transcribe`` call, and records the arguments."""

    def __init__(self, *scripted):
        self.scripted = list(scripted)
        self.calls: list[dict] = []

    def transcribe(self, audio, **kwargs):
        self.calls.append({"audio": audio, **kwargs})
        segments, inf = self.scripted.pop(0)
        return iter(segments), inf


def make_engine(model: StubModel, **settings) -> WhisperEngine:
    return WhisperEngine(make_settings(device="cpu", **settings), model_factory=lambda s, d, c: model)


def test_model_is_loaded_lazily_with_resolved_device_settings():
    built = []

    def factory(settings, device, compute_type):
        built.append((device, compute_type))
        return StubModel(([seg("สวัสดี")], info()), ([seg("สวัสดี")], info()))

    engine = WhisperEngine(make_settings(device="cpu", compute_type="auto"), model_factory=factory)
    assert not engine.loaded and built == []
    engine.transcribe(np.zeros(1600, dtype=np.float32), "th")
    engine.transcribe(np.zeros(1600, dtype=np.float32), "th")
    assert engine.loaded and built == [("cpu", "int8")]  # built once, reused
    assert (engine.device, engine.compute_type) == ("cpu", "int8")


def test_device_resolution():
    assert _resolve_device("cuda") == "cuda" and _resolve_device("cpu") == "cpu"
    assert _resolve_device("auto") in ("cuda", "cpu")


def test_auto_compute_type_follows_what_the_cuda_build_supports(monkeypatch):
    import ctranslate2

    def supported(types):
        monkeypatch.setattr(ctranslate2, "get_supported_compute_types", lambda device: types)

    supported({"float16", "int8_float16", "int8_float32", "int8"})  # Volta and newer
    assert _resolve_compute_type("auto", "cuda") == "float16"
    supported({"int8_float32", "int8", "float32"})  # GTX 1050 (Pascal): no fp16 kernels
    assert _resolve_compute_type("auto", "cuda") == "int8_float32"
    supported(set())  # cannot query -> the safest type
    assert _resolve_compute_type("auto", "cuda") == "int8"
    assert _resolve_compute_type("auto", "cpu") == "int8"
    assert _resolve_compute_type("float16", "cuda") == "float16"  # explicit setting is never overridden


def test_thai_transcript_joins_segments_and_passes_decoding_options():
    model = StubModel(([seg(" ท่อระบายน้ำ", 0, 1.2), seg("แตก", 1.2, 2.0)], info(duration=2.0)))
    engine = make_engine(model, beam_size=3, initial_prompt="คำใบ้", vad_filter=True)
    out = engine.transcribe(np.zeros(16000, dtype=np.float32), "th")
    assert out.text == "ท่อระบายน้ำแตก"
    assert out.language == "th" and out.duration == 2.0
    assert [s["text"] for s in out.segments] == ["ท่อระบายน้ำ", "แตก"]
    call = model.calls[0]
    assert call["language"] == "th" and call["beam_size"] == 3 and call["vad_filter"] is True
    assert call["initial_prompt"] == "คำใบ้" and call["condition_on_previous_text"] is False


def test_english_words_keep_their_spaces():
    model = StubModel(([seg(" There is a broken"), seg(" water pipe")], info("en")))
    out = make_engine(model).transcribe(np.zeros(16000, dtype=np.float32), "en")
    assert out.text == "There is a broken water pipe"


def test_empty_initial_prompt_is_not_sent():
    model = StubModel(([seg("x")], info()))
    make_engine(model, initial_prompt="").transcribe(np.zeros(100, dtype=np.float32), "th")
    assert model.calls[0]["initial_prompt"] is None


def test_auto_accepts_english_with_a_single_pass_and_no_thai_prompt():
    model = StubModel(([seg("hello")], info("en")))
    out = make_engine(model, initial_prompt="คำใบ้").transcribe(np.zeros(100, dtype=np.float32), "auto")
    assert out.language == "en" and len(model.calls) == 1
    assert model.calls[0]["language"] is None and model.calls[0]["initial_prompt"] is None


def test_auto_detects_without_prompt_then_decodes_thai_with_the_prompt():
    model = StubModel(([seg("ignored")], info("th")), ([seg("ไฟดับ")], info("th", 1.0)))
    out = make_engine(model, initial_prompt="คำใบ้").transcribe(np.zeros(100, dtype=np.float32), "auto")
    assert out.text == "ไฟดับ"
    assert [(c["language"], c["initial_prompt"]) for c in model.calls] == [(None, None), ("th", "คำใบ้")]


def test_thai_prompt_is_never_used_for_english():
    model = StubModel(([seg("pipe")], info("en")))
    make_engine(model, initial_prompt="คำใบ้").transcribe(np.zeros(100, dtype=np.float32), "en")
    assert model.calls[0]["language"] == "en" and model.calls[0]["initial_prompt"] is None


def test_auto_redecodes_as_thai_when_detection_is_outside_allowed_languages():
    model = StubModel(
        ([seg("こんにちは")], info("ja", 0.51)),  # Whisper mislabelled Thai phone audio
        ([seg("แจ้งไฟดับ")], info("th", 1.0)),
    )
    out = make_engine(
        model, allowed_languages=("th", "en"), fallback_language="th", initial_prompt="คำใบ้"
    ).transcribe(np.zeros(100, dtype=np.float32), None)
    assert out.text == "แจ้งไฟดับ" and out.language == "th"
    assert [(c["language"], c["initial_prompt"]) for c in model.calls] == [(None, None), ("th", "คำใบ้")]


def test_default_language_setting_is_used_when_none_requested():
    model = StubModel(([seg("ok")], info("th")))
    make_engine(model, language="th").transcribe(np.zeros(100, dtype=np.float32), None)
    assert model.calls[0]["language"] == "th"


def test_silence_hallucination_segments_are_dropped():
    model = StubModel(
        ([seg("ขอบคุณที่รับชม", no_speech_prob=0.95, avg_logprob=-1.6), seg("ไฟดับ", no_speech_prob=0.1)], info())
    )
    out = make_engine(model).transcribe(np.zeros(100, dtype=np.float32), "th")
    assert out.text == "ไฟดับ" and len(out.segments) == 1


def test_all_silence_gives_empty_text():
    model = StubModel(([], info(probability=0.3, duration=1.0)))
    out = make_engine(model).transcribe(np.zeros(100, dtype=np.float32), "th")
    assert out.text == "" and out.segments == []


def test_bytes_are_wrapped_as_a_file_object_and_arrays_pass_through():
    model = StubModel(([seg("a")], info()), ([seg("b")], info()))
    engine = make_engine(model)
    engine.transcribe(b"RIFF....", "th")
    samples = np.zeros(10, dtype=np.float32)
    engine.transcribe(samples, "th")
    assert isinstance(model.calls[0]["audio"], io.BytesIO)
    assert model.calls[1]["audio"] is samples


def test_redecode_gets_a_fresh_file_object():
    model = StubModel(([seg("x")], info("th")), ([seg("y")], info("th")))
    make_engine(model, initial_prompt="คำใบ้").transcribe(b"data", None)  # detect, then decode again with prompt
    first, second = model.calls[0]["audio"], model.calls[1]["audio"]
    assert first is not second and second.read() == b"data"


def test_model_load_failure_is_reported():
    def boom(*_):
        raise OSError("no such model")

    engine = WhisperEngine(make_settings(device="cpu"), model_factory=boom)
    with pytest.raises(ModelLoadError) as exc:
        engine.transcribe(np.zeros(10, dtype=np.float32), "th")
    assert exc.value.status == 503 and not engine.loaded


def test_pyav_decode_errors_map_to_audio_decode_error():
    class InvalidDataError(Exception):
        __module__ = "av.error"

    class BadModel:
        def transcribe(self, *_a, **_k):
            raise InvalidDataError("not audio")

    engine = WhisperEngine(make_settings(device="cpu"), model_factory=lambda *_: BadModel())
    with pytest.raises(AudioDecodeError) as exc:
        engine.transcribe(b"not audio", "th")
    assert exc.value.status == 422


def test_other_failures_are_wrapped_as_asr_error():
    class BadModel:
        def transcribe(self, *_a, **_k):
            raise RuntimeError("CUDA out of memory")

    engine = WhisperEngine(make_settings(device="cpu"), model_factory=lambda *_: BadModel())
    with pytest.raises(ASRError) as exc:
        engine.transcribe(np.zeros(10, dtype=np.float32), "th")
    assert exc.value.status == 500 and "CUDA" in str(exc.value)
