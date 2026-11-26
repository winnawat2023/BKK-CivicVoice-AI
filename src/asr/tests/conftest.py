"""Shared fixtures: a fake Whisper engine and a fake CivicVoice API, so no model or network is needed."""

from __future__ import annotations

import json
from typing import Any

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from asr_service.app import create_app
from asr_service.audio import WHISPER_RATE
from asr_service.config import Settings
from asr_service.engine import Transcript

THAI_TEXT = "ท่อระบายน้ำแตก ซอยสุขุมวิท 50"


class FakeEngine:
    """Stands in for WhisperEngine. ``result`` may be a Transcript or an exception to raise."""

    def __init__(self, result: Transcript | Exception | None = None) -> None:
        self.result = result or Transcript(text=THAI_TEXT, language="th", language_probability=0.99, duration=2.0)
        self.calls: list[tuple[Any, str | None]] = []
        self.loaded = True
        self.device = "cpu"
        self.compute_type = "int8"

    def load(self) -> None:
        self.loaded = True

    def transcribe(self, audio: Any, language: str | None = None) -> Transcript:
        self.calls.append((audio, language))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeBackend:
    """Records what the ASR service sends to the CivicVoice API."""

    def __init__(self, status: int = 200, error: Exception | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.status = status
        self.error = error

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error:
            raise self.error
        return httpx.Response(self.status, json={"success": True})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.content]


def make_settings(**overrides) -> Settings:
    values: dict[str, Any] = dict(
        backend_url="http://backend.test",
        partial_interval_ms=100_000,  # no partials unless a test asks for them
        endpoint_silence_ms=700,
    )
    values.update(overrides)
    return Settings(**values)


def tone(seconds: float, amplitude: float = 0.2, rate: int = WHISPER_RATE) -> np.ndarray:
    t = np.arange(int(seconds * rate)) / rate
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def silence(seconds: float, rate: int = WHISPER_RATE) -> np.ndarray:
    return np.zeros(int(seconds * rate), dtype=np.float32)


def to_pcm16(samples: np.ndarray) -> bytes:
    return (samples * 32767).astype("<i2").tobytes()


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def make_client(engine, backend):
    clients: list[TestClient] = []

    def _make(settings: Settings | None = None, *, eng=None, back=None) -> TestClient:
        app = create_app(
            settings or make_settings(),
            engine=eng or engine,
            backend_transport=(back or backend).transport,
        )
        tc = TestClient(app)
        tc.__enter__()
        clients.append(tc)
        return tc

    yield _make
    for tc in clients:
        tc.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()
