"""Guards the real audio-decoding stack (faster-whisper + PyAV). No model is loaded, so it is fast.

faster-whisper 1.2.x passes ``metadata_errors=`` to ``av.open``; PyAV 19 dropped that argument, which turned every
uploaded file into an HTTP 500. The fakes in the other tests cannot see that kind of break, this one can.
"""

import io
import wave

import numpy as np
import pytest

faster_whisper_audio = pytest.importorskip("faster_whisper.audio")


def wav_bytes(samples: np.ndarray, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((samples * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def test_wav_upload_decodes_and_resamples_to_16khz():
    t = np.arange(8000 * 2) / 8000  # 2 s of 8 kHz telephony-rate audio
    data = wav_bytes(0.3 * np.sin(2 * np.pi * 440 * t), 8000)
    audio = faster_whisper_audio.decode_audio(io.BytesIO(data))
    assert audio.dtype == np.float32
    assert abs(audio.size - 2 * 16000) < 400
    assert float(np.abs(audio).max()) > 0.2
