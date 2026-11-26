import numpy as np
import pytest

from asr_service.audio import (
    decode_audio,
    mulaw_to_float32,
    pcm16_to_float32,
    resample,
)


def test_pcm16_roundtrip_and_range():
    raw = np.array([0, 16384, -16384, 32767, -32768], dtype="<i2").tobytes()
    out = pcm16_to_float32(raw)
    assert out.dtype == np.float32
    assert out.tolist() == pytest.approx([0.0, 0.5, -0.5, 32767 / 32768, -1.0])


def test_pcm16_drops_trailing_odd_byte_and_handles_empty():
    assert pcm16_to_float32(b"\x00\x40\x01").size == 1
    assert pcm16_to_float32(b"").size == 0
    assert pcm16_to_float32(b"\x01").size == 0


def test_mulaw_known_g711_values():
    # 0xFF is mu-law "zero"; 0x00 / 0x80 are the most negative / most positive codes (+-32124).
    out = mulaw_to_float32(bytes([0xFF, 0x00, 0x80, 0x7F]))
    assert out[0] == 0.0
    assert out[1] == pytest.approx(-32124 / 32768)
    assert out[2] == pytest.approx(32124 / 32768)
    assert out[3] == 0.0  # 0x7F is negative zero


def test_mulaw_is_monotonic_within_sign():
    codes = bytes(range(0x80, 0xFF))  # positive half, loudest -> quietest
    out = mulaw_to_float32(codes)
    assert np.all(np.diff(out) <= 0)
    assert mulaw_to_float32(b"").size == 0


def test_decode_audio_dispatch_and_unknown_encoding():
    assert decode_audio(b"\xff", "mulaw").size == 1
    assert decode_audio(b"\x00\x00", "pcm16").size == 1
    with pytest.raises(ValueError):
        decode_audio(b"\x00", "opus")


def test_resample_identity_up_and_down():
    x = np.linspace(-1, 1, 8000, dtype=np.float32)
    assert resample(x, 16000) is not None and resample(x, 16000).size == 8000  # same rate: untouched
    assert resample(x, 8000).size == 16000  # 8 kHz telephony -> 16 kHz
    assert resample(np.ones(48000, dtype=np.float32), 48000).size == 16000  # integer factor 3
    assert resample(np.ones(48000, dtype=np.float32), 48000).tolist() == pytest.approx([1.0] * 16000)
    assert resample(np.zeros(44100, dtype=np.float32), 44100).size == 16000  # non-integer ratio
    assert resample(np.zeros(0, dtype=np.float32), 8000).size == 0


def test_resample_rejects_bad_rate():
    with pytest.raises(ValueError):
        resample(np.zeros(10, dtype=np.float32), 0)
