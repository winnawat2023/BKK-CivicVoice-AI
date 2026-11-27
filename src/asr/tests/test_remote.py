"""Remote engine (existing Thai ASR service on DGX 100): contract, language rules, errors, and the app wired to it."""

from __future__ import annotations

import httpx
import numpy as np
import pytest

from asr_service.app import create_app
from asr_service.audio import WHISPER_RATE
from asr_service.config import Settings
from asr_service.engine import ModelLoadError
from asr_service.remote import RemoteEngine, RemoteFailedError, RemoteUnavailableError, UnsupportedLanguageError

REMOTE_TEXT = "ท่อระบายน้ำแตก  ซอยสุขุมวิท 50"


class FakeRemote:
    """Stands in for the DGX 100 service: /healthz and /transcribe/file, with switches to simulate failures."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.health_body: dict = {"status": "ok", "device": "cuda", "model_loaded": True}
        self.health_error: Exception | None = None
        self.transcribe_status = 200
        self.transcribe_error: Exception | None = None
        self.transcribe_body: dict = {
            "status": "success",
            "processing_time_s": 0.5,
            "text": REMOTE_TEXT,
            "chunks": [
                {"timestamp": [0.0, 2.5], "text": "ท่อระบายน้ำแตก"},
                {"timestamp": [2.5, 4.0], "text": " ซอยสุขุมวิท 50"},
            ],
        }

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/healthz":
            if self.health_error:
                raise self.health_error
            return httpx.Response(200, json=self.health_body)
        if request.url.path == "/transcribe/file":
            if self.transcribe_error:
                raise self.transcribe_error
            if self.transcribe_status != 200:
                return httpx.Response(self.transcribe_status, text="internal error")
            return httpx.Response(200, json=self.transcribe_body)
        return httpx.Response(404)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def transcribe_requests(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path == "/transcribe/file"]


def make_settings(**overrides) -> Settings:
    values = dict(
        engine="remote",
        remote_url="http://remote.test",
        backend_url="http://backend.test",
        partial_interval_ms=100_000,
    )
    values.update(overrides)
    return Settings(**values)


def make_engine(fake: FakeRemote, **overrides) -> RemoteEngine:
    return RemoteEngine(make_settings(**overrides), transport=fake.transport)


def multipart_has(request: httpx.Request, fragment: bytes) -> bool:
    return fragment in request.content


def test_load_reads_device_from_healthz():
    fake = FakeRemote()
    engine = make_engine(fake)
    assert not engine.loaded
    engine.load()
    assert engine.loaded
    assert engine.device == "cuda"
    assert engine.compute_type == "remote"


def test_bytes_are_sent_as_thai_and_mapped_to_transcript():
    fake = FakeRemote()
    out = make_engine(fake).transcribe(b"RIFF-fake-audio", language="th")

    assert out.text == "ท่อระบายน้ำแตก ซอยสุขุมวิท 50"  # whitespace collapsed
    assert out.language == "th"
    assert out.duration == 4.0  # from the last chunk end
    assert out.segments == [
        {"start": 0.0, "end": 2.5, "text": "ท่อระบายน้ำแตก"},
        {"start": 2.5, "end": 4.0, "text": "ซอยสุขุมวิท 50"},
    ]
    (post,) = fake.transcribe_requests()
    assert multipart_has(post, b'name="language"\r\n\r\nth')
    assert multipart_has(post, b'filename="audio.bin"')


def test_auto_and_missing_language_are_treated_as_thai():
    fake = FakeRemote()
    engine = make_engine(fake, language="auto")
    out = engine.transcribe(b"RIFF-fake-audio", language=None)
    assert out.language == "th"
    assert multipart_has(fake.transcribe_requests()[0], b'name="language"\r\n\r\nth')


def test_english_is_refused_without_calling_the_remote():
    fake = FakeRemote()
    engine = make_engine(fake)
    with pytest.raises(UnsupportedLanguageError) as info:
        engine.transcribe(b"RIFF-fake-audio", language="en")
    assert info.value.status == 422
    assert fake.transcribe_requests() == []


def test_float_samples_are_sent_as_wav_and_duration_comes_from_samples():
    fake = FakeRemote()
    samples = np.zeros(WHISPER_RATE, dtype=np.float32)  # exactly one second
    out = make_engine(fake).transcribe(samples, language="th")

    (post,) = fake.transcribe_requests()
    assert multipart_has(post, b'filename="utterance.wav"')
    assert multipart_has(post, b"RIFF") and multipart_has(post, b"WAVE")
    assert out.duration == 1.0


def test_unreachable_health_check_is_a_model_load_error():
    fake = FakeRemote()
    fake.health_error = httpx.ConnectError("connection refused")
    engine = make_engine(fake)
    with pytest.raises(ModelLoadError) as info:
        engine.load()
    assert info.value.status == 503
    assert not engine.loaded


def test_remote_not_ready_is_a_model_load_error():
    fake = FakeRemote()
    fake.health_body = {"status": "ok", "device": "cuda", "model_loaded": False}
    with pytest.raises(ModelLoadError):
        make_engine(fake).load()


def test_remote_http_error_is_502():
    fake = FakeRemote()
    fake.transcribe_status = 500
    with pytest.raises(RemoteFailedError) as info:
        make_engine(fake).transcribe(b"RIFF-fake-audio", language="th")
    assert info.value.status == 502


def test_remote_timeout_is_503():
    fake = FakeRemote()
    fake.transcribe_error = httpx.ReadTimeout("too slow")
    with pytest.raises(RemoteUnavailableError) as info:
        make_engine(fake).transcribe(b"RIFF-fake-audio", language="th")
    assert info.value.status == 503


def test_remote_status_other_than_success_is_502():
    fake = FakeRemote()
    fake.transcribe_body = {"status": "error", "text": ""}
    with pytest.raises(RemoteFailedError):
        make_engine(fake).transcribe(b"RIFF-fake-audio", language="th")


def test_app_transcribes_through_the_remote_engine_and_forwards(make_client, backend):
    fake = FakeRemote()
    settings = make_settings()
    client = make_client(settings, eng=RemoteEngine(settings, transport=fake.transport))

    r = client.post(
        "/v1/transcribe",
        files={"file": ("call.wav", b"RIFF-fake-audio", "audio/wav")},
        data={"interaction_id": "CALL-R1", "language": "th"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["text"] == "ท่อระบายน้ำแตก ซอยสุขุมวิท 50"
    assert body["forwarded"]["ok"] is True
    assert any(req.url.path == "/api/v1/calls/CALL-R1/segments" for req in backend.requests)


def test_app_returns_422_for_english_upload(make_client):
    fake = FakeRemote()
    settings = make_settings()
    client = make_client(settings, eng=RemoteEngine(settings, transport=fake.transport))

    r = client.post(
        "/v1/transcribe",
        files={"file": ("call.wav", b"RIFF-fake-audio", "audio/wav")},
        data={"language": "en"},
    )
    assert r.status_code == 422


def test_create_app_picks_the_engine_from_settings():
    app = create_app(make_settings(engine="remote"), backend_transport=FakeRemote().transport)
    assert isinstance(app.state.engine, RemoteEngine)


def test_unknown_engine_name_is_rejected():
    with pytest.raises(ValueError, match="ASR_ENGINE"):
        create_app(make_settings(engine="bogus"))


def test_from_env_reads_remote_settings(monkeypatch):
    monkeypatch.setenv("ASR_ENGINE", "remote")
    monkeypatch.setenv("ASR_REMOTE_URL", "http://192.168.200.100:5001/")
    monkeypatch.setenv("ASR_REMOTE_TIMEOUT_S", "12")
    settings = Settings.from_env()
    assert settings.engine == "remote"
    assert settings.remote_url == "http://192.168.200.100:5001"
    assert settings.remote_timeout_s == 12.0
