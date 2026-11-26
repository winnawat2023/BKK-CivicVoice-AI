"""Audio helpers for the live stream: G.711 mu-law / PCM16 decoding and resampling to 16 kHz.

Whisper wants mono float32 at 16 kHz. Genesys telephony audio is 8 kHz G.711 mu-law, so the
streaming endpoint converts whatever the client sends into that shape. Uploaded files do not
come through here: faster-whisper decodes and resamples those itself (PyAV).
"""

from __future__ import annotations

import numpy as np

WHISPER_RATE = 16000
SUPPORTED_ENCODINGS = ("pcm16", "mulaw")


def pcm16_to_float32(data: bytes) -> np.ndarray:
    """Little-endian signed 16-bit PCM -> float32 in [-1, 1). A trailing odd byte is dropped."""
    usable = len(data) - (len(data) % 2)
    if usable <= 0:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(data[:usable], dtype="<i2").astype(np.float32) / 32768.0


def mulaw_to_float32(data: bytes) -> np.ndarray:
    """ITU-T G.711 mu-law bytes -> float32 in [-1, 1)."""
    if not data:
        return np.zeros(0, dtype=np.float32)
    u = np.invert(np.frombuffer(data, dtype=np.uint8)).astype(np.int32)
    magnitude = (((u & 0x0F) << 3) + 0x84) << ((u & 0x70) >> 4)
    sample = np.where(u & 0x80, 0x84 - magnitude, magnitude - 0x84)
    return (sample.astype(np.float32) / 32768.0).clip(-1.0, 1.0)


def decode_audio(data: bytes, encoding: str) -> np.ndarray:
    if encoding == "pcm16":
        return pcm16_to_float32(data)
    if encoding == "mulaw":
        return mulaw_to_float32(data)
    raise ValueError(f"unsupported encoding {encoding!r}; use one of {SUPPORTED_ENCODINGS}")


def resample(samples: np.ndarray, src_rate: int, dst_rate: int = WHISPER_RATE) -> np.ndarray:
    """Mono resampler. Integer down-sampling averages blocks (cheap anti-alias); the rest is linear."""
    if src_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if src_rate == dst_rate or samples.size == 0:
        return samples.astype(np.float32, copy=False)
    if src_rate > dst_rate and src_rate % dst_rate == 0:
        factor = src_rate // dst_rate
        usable = (samples.size // factor) * factor
        if usable == 0:
            return np.zeros(0, dtype=np.float32)
        return samples[:usable].reshape(-1, factor).mean(axis=1).astype(np.float32)
    out_len = int(round(samples.size * dst_rate / src_rate))
    if out_len == 0:
        return np.zeros(0, dtype=np.float32)
    positions = np.linspace(0, samples.size - 1, num=out_len)
    return np.interp(positions, np.arange(samples.size), samples).astype(np.float32)
