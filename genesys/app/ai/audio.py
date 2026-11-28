"""Tiny pure-Python audio helpers (G.711 mu-law + linear resampling).

The recommended configuration is ``OPENAI_AUDIO_FORMAT=pcmu``: Genesys already
speaks G.711 mu-law at 8 kHz and the OpenAI Realtime API accepts/produces
``audio/pcmu`` directly, so no conversion is needed.  These helpers exist for
the ``pcm`` mode (OpenAI ``audio/pcm`` is 24 kHz mono) and for debugging.
"""

from __future__ import annotations

import struct

ULAW_BIAS = 0x84
ULAW_CLIP = 32635


def _build_ulaw_decode_table() -> tuple[int, ...]:
    table = []
    for value in range(256):
        u = ~value & 0xFF
        sign = u & 0x80
        exponent = (u >> 4) & 0x07
        mantissa = u & 0x0F
        sample = ((mantissa << 3) + ULAW_BIAS) << exponent
        sample -= ULAW_BIAS
        if sign:
            sample = -sample
        table.append(sample)
    return tuple(table)


_ULAW_DECODE = _build_ulaw_decode_table()


def ulaw_to_pcm16(data: bytes) -> bytes:
    """Decode G.711 mu-law bytes into little-endian signed 16-bit PCM."""

    samples = [_ULAW_DECODE[b] for b in data]
    return struct.pack(f"<{len(samples)}h", *samples)


def _linear_to_ulaw(sample: int) -> int:
    if sample < 0:
        sample = -sample
        sign = 0x80
    else:
        sign = 0x00
    sample = min(sample, ULAW_CLIP) + ULAW_BIAS

    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        exponent -= 1
        mask >>= 1

    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def pcm16_to_ulaw(data: bytes) -> bytes:
    """Encode little-endian signed 16-bit PCM into G.711 mu-law bytes."""

    count = len(data) // 2
    samples = struct.unpack(f"<{count}h", data[: count * 2])
    return bytes(_linear_to_ulaw(s) for s in samples)


def resample_pcm16(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Linear-interpolation resampler for little-endian signed 16-bit PCM."""

    if src_rate == dst_rate or not data:
        return data

    count = len(data) // 2
    samples = struct.unpack(f"<{count}h", data[: count * 2])
    if count == 0:
        return b""

    ratio = dst_rate / src_rate
    out_count = max(int(count * ratio), 1)
    last = count - 1
    out = []
    for i in range(out_count):
        pos = i / ratio
        idx = int(pos)
        frac = pos - idx
        if idx >= last:
            out.append(samples[last])
            continue
        s0 = samples[idx]
        s1 = samples[idx + 1]
        out.append(int(s0 + (s1 - s0) * frac))
    return struct.pack(f"<{len(out)}h", *out)


def silence_ulaw(duration_ms: int, sample_rate: int = 8000) -> bytes:
    """Return silence as G.711 mu-law bytes (0xFF is the mu-law zero code)."""

    count = int(sample_rate * duration_ms / 1000)
    return b"\xff" * count
