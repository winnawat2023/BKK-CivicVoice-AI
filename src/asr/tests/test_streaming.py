import numpy as np

from asr_service.audio import WHISPER_RATE
from asr_service.streaming import UtteranceSegmenter

from .conftest import silence, make_settings, tone


def kinds(events):
    return [e.kind for e in events]


def test_silence_produces_nothing():
    seg = UtteranceSegmenter(make_settings())
    assert seg.feed(silence(3)) == []
    assert seg.flush() == []


def test_short_noise_burst_is_ignored():
    seg = UtteranceSegmenter(make_settings(min_speech_ms=250))
    events = seg.feed(np.concatenate([tone(0.1), silence(1.5)]))
    assert events == []


def test_speech_then_pause_gives_one_final_including_preroll():
    seg = UtteranceSegmenter(make_settings())
    events = seg.feed(np.concatenate([silence(0.5), tone(1.0), silence(1.0)]))
    assert kinds(events) == ["final"]
    # ~1 s of speech + 0.3 s pre-roll + the 0.7 s of silence that ended the utterance
    assert 1.8 < events[0].seconds < 2.2


def test_two_utterances_give_two_finals():
    seg = UtteranceSegmenter(make_settings())
    audio = np.concatenate([tone(0.8), silence(1.0), tone(0.8), silence(1.0)])
    assert kinds(seg.feed(audio)) == ["final", "final"]


def test_partials_while_speaking_then_final():
    seg = UtteranceSegmenter(make_settings(partial_interval_ms=500))
    events = seg.feed(np.concatenate([tone(2.0), silence(1.0)]))
    assert kinds(events)[-1] == "final"
    partials = [e for e in events if e.kind == "partial"]
    assert len(partials) >= 3
    assert all(a.audio.size < b.audio.size for a, b in zip(partials, partials[1:]))  # each one is longer


def test_long_speech_is_cut_at_max_utterance():
    seg = UtteranceSegmenter(make_settings(max_utterance_s=2.0))
    events = seg.feed(tone(5.0))
    finals = [e for e in events if e.kind == "final"]
    assert len(finals) == 2
    assert all(f.seconds <= 2.05 for f in finals)


def test_flush_finalises_open_utterance_once():
    seg = UtteranceSegmenter(make_settings())
    assert seg.feed(tone(1.0)) == []
    flushed = seg.flush()
    assert kinds(flushed) == ["final"]
    assert seg.flush() == []


def test_tiny_chunks_behave_like_one_big_feed():
    audio = np.concatenate([silence(0.3), tone(1.0), silence(1.0), tone(0.6), silence(1.0)])
    big = UtteranceSegmenter(make_settings()).feed(audio)
    small_seg = UtteranceSegmenter(make_settings())
    small = []
    for i in range(0, audio.size, 137):  # odd size: frames straddle chunk boundaries
        small.extend(small_seg.feed(audio[i : i + 137]))
    assert kinds(big) == kinds(small) == ["final", "final"]
    assert abs(big[0].audio.size - small[0].audio.size) <= WHISPER_RATE * 0.03
