import asyncio
import io
import wave

import pytest

from app.ai.typhoon import TyphoonVLLMBridge, _decode_audio_to_pcm16, _pcm16_rms, _wav_bytes
from app.config import Settings


def make_bridge(**overrides):
    settings = Settings(
        _env_file="__missing__.env",
        ai_provider="typhoon",
        typhoon_base_url="http://127.0.0.1:8001/v1",
        typhoon_stt_base_url="http://127.0.0.1:5001/v1",
        typhoon_tts_provider="openai",
        typhoon_vad_silence_ms=200,
        typhoon_vad_energy_threshold=100,
        **overrides,
    )
    audio = bytearray()
    barge = []
    bot = []
    caller = []

    async def on_audio(data: bytes) -> None:
        audio.extend(data)

    async def on_barge_in() -> None:
        barge.append(True)

    async def on_bot_text(text: str) -> None:
        bot.append(text)

    async def on_caller_text(text: str) -> None:
        caller.append(text)

    bridge = TyphoonVLLMBridge(settings, on_audio, on_barge_in, on_bot_text, on_caller_text)
    return bridge, settings, audio, barge, bot, caller


def test_wav_roundtrip_and_rms():
    pcm = b"\x00\x10" * 160
    wav = _wav_bytes(pcm, 8000)
    decoded, rate = _decode_audio_to_pcm16(wav, "audio/wav")
    assert rate == 8000
    assert decoded == pcm
    assert _pcm16_rms(pcm) > 0


@pytest.mark.asyncio
async def test_vad_flushes_utterance_to_queue():
    bridge, *_ = make_bridge()
    from app.ai.audio import pcm16_to_ulaw

    # 20ms 8kHz PCM16 loud frame.
    pcm_loud = (b"\x00\x30" * 160)

    ulaw_loud = pcm16_to_ulaw(pcm_loud)
    ulaw_silence = b"\xff" * 160  # ulaw silence

    # 300ms speech
    for _ in range(15):
        await bridge.send_audio(ulaw_loud)
    # 300ms silence, should flush (silence_ms=200)
    for _ in range(15):
        await bridge.send_audio(ulaw_silence)

    item = await asyncio.wait_for(bridge._turns.get(), timeout=1.0)
    assert isinstance(item, (bytes, bytearray))
    assert len(item) > 0