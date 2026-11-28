import struct

from app.ai.audio import (
    pcm16_to_ulaw,
    resample_pcm16,
    silence_ulaw,
    ulaw_to_pcm16,
)


def test_zero_encodes_to_ulaw_zero_code():
    assert pcm16_to_ulaw(struct.pack("<h", 0)) == b"\xff"


def test_ulaw_zero_decodes_to_zero():
    assert struct.unpack("<h", ulaw_to_pcm16(b"\xff"))[0] == 0


def test_small_values_roundtrip_within_quantization_error():
    for sample in (100, -100, 500, -500, 2000, -2000):
        encoded = pcm16_to_ulaw(struct.pack("<h", sample))
        decoded = struct.unpack("<h", ulaw_to_pcm16(encoded))[0]
        assert abs(decoded - sample) <= 64, (sample, decoded)


def test_resample_changes_length_proportionally():
    samples = 800  # 100ms @ 8kHz
    pcm = struct.pack(f"<{samples}h", *([1000] * samples))
    up = resample_pcm16(pcm, 8000, 24000)
    assert len(up) == samples * 3 * 2

    down = resample_pcm16(up, 24000, 8000)
    assert len(down) == samples * 2


def test_resample_identity():
    pcm = struct.pack("<4h", 0, 100, -100, 50)
    assert resample_pcm16(pcm, 8000, 8000) is pcm


def test_silence_length():
    assert silence_ulaw(200) == b"\xff" * 1600
