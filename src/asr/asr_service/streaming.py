"""Turn a continuous 16 kHz audio stream into utterances (partial and final) for Whisper.

Whisper is not a streaming model, so live captions work by cutting the call audio into utterances with a small
energy detector, re-decoding the utterance so far every ``partial_interval_ms`` (partial) and decoding it once more
when the caller pauses (final). This module is pure (no model, no I/O) so it is easy to test.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

import numpy as np

from .audio import WHISPER_RATE
from .config import Settings

FRAME_MS = 30
PRE_ROLL_MS = 300  # audio kept from just before speech starts, so the first syllable is not clipped


@dataclass
class Utterance:
    kind: Literal["partial", "final"]
    audio: np.ndarray  # mono float32 @ 16 kHz, the whole utterance so far

    @property
    def seconds(self) -> float:
        return self.audio.size / WHISPER_RATE


class UtteranceSegmenter:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self._frame = WHISPER_RATE * FRAME_MS // 1000
        self._carry = np.zeros(0, dtype=np.float32)
        self._pre: deque[np.ndarray] = deque(maxlen=max(1, PRE_ROLL_MS // FRAME_MS))
        self._reset()

    def _reset(self) -> None:
        self._in_speech = False
        self._frames: list[np.ndarray] = []
        self._speech_ms = 0
        self._silence_ms = 0
        self._since_partial_ms = 0

    # ---------------------------------------------------------------- public
    def feed(self, samples: np.ndarray) -> list[Utterance]:
        """Add 16 kHz mono float32 samples; returns the partial/final utterances that became ready."""
        out: list[Utterance] = []
        data = np.concatenate([self._carry, samples]) if self._carry.size else samples
        usable = (data.size // self._frame) * self._frame
        self._carry = data[usable:].copy()
        for i in range(0, usable, self._frame):
            self._on_frame(data[i : i + self._frame], out)
        return out

    def flush(self) -> list[Utterance]:
        """End of stream: finish any utterance that is still open."""
        out: list[Utterance] = []
        self._carry = np.zeros(0, dtype=np.float32)
        if self._in_speech and self._speech_ms >= self.s.min_speech_ms:
            out.append(Utterance("final", np.concatenate(self._frames)))
        self._pre.clear()
        self._reset()
        return out

    # --------------------------------------------------------------- internals
    def _on_frame(self, frame: np.ndarray, out: list[Utterance]) -> None:
        is_speech = float(np.sqrt(np.mean(np.square(frame)))) >= self.s.energy_threshold

        if not self._in_speech:
            if is_speech:
                self._in_speech = True
                self._frames = [*self._pre, frame]
                self._pre.clear()
                self._speech_ms = FRAME_MS
                self._silence_ms = 0
                self._since_partial_ms = FRAME_MS
            else:
                self._pre.append(frame)
            return

        self._frames.append(frame)
        self._since_partial_ms += FRAME_MS
        if is_speech:
            self._speech_ms += FRAME_MS
            self._silence_ms = 0
        else:
            self._silence_ms += FRAME_MS

        length_s = len(self._frames) * FRAME_MS / 1000
        if self._silence_ms >= self.s.endpoint_silence_ms or length_s >= self.s.max_utterance_s:
            if self._speech_ms >= self.s.min_speech_ms:
                out.append(Utterance("final", np.concatenate(self._frames)))
            self._reset()
        elif (
            self._since_partial_ms >= self.s.partial_interval_ms
            and self._speech_ms >= self.s.min_speech_ms
            and self._silence_ms == 0
        ):
            out.append(Utterance("partial", np.concatenate(self._frames)))
            self._since_partial_ms = 0
