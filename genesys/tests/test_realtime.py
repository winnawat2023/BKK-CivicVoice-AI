import base64

import pytest

from app.ai.realtime import RealtimeBridge
from app.config import Settings


def make_bridge():
    audio = []
    barge_ins = []
    bot_texts = []
    caller_texts = []

    async def on_audio(data: bytes) -> None:
        audio.append(data)

    async def on_barge_in() -> None:
        barge_ins.append(True)

    async def on_bot_text(text: str) -> None:
        bot_texts.append(text)

    async def on_caller_text(text: str) -> None:
        caller_texts.append(text)

    bridge = RealtimeBridge(
        settings=Settings(),
        on_audio=on_audio,
        on_barge_in=on_barge_in,
        on_bot_text=on_bot_text,
        on_caller_text=on_caller_text,
    )
    return bridge, audio, barge_ins, bot_texts, caller_texts


def audio_delta_event(payload: bytes) -> dict:
    return {
        "type": "response.output_audio.delta",
        "delta": base64.b64encode(payload).decode("ascii"),
    }


@pytest.mark.asyncio
async def test_pcmu_output_is_passed_through_untouched():
    bridge, audio, barge_ins, bot_texts, caller_texts = make_bridge()
    payload = b"\xff" * 160  # 20 ms of PCMU silence

    await bridge._handle_event(audio_delta_event(payload))

    assert audio == [payload]
    assert barge_ins == []
    assert bridge._playing is True


@pytest.mark.asyncio
async def test_speech_started_triggers_barge_in_and_mutes_stale_audio():
    bridge, audio, barge_ins, bot_texts, caller_texts = make_bridge()
    payload = b"\x01" * 160

    await bridge._handle_event(audio_delta_event(payload))
    await bridge._handle_event({"type": "input_audio_buffer.speech_started"})

    assert barge_ins == [True]
    assert bridge._muting is True

    # Audio that arrives for the interrupted response must be dropped.
    await bridge._handle_event(audio_delta_event(b"\x02" * 160))
    assert audio == [payload]

    # The cancellation completes with response.done, un-muting the bridge.
    await bridge._handle_event({"type": "response.done"})
    assert bridge._muting is False
    assert bridge._playing is False


@pytest.mark.asyncio
async def test_transcripts_are_forwarded():
    bridge, audio, barge_ins, bot_texts, caller_texts = make_bridge()

    await bridge._handle_event(
        {"type": "response.output_audio_transcript.done", "transcript": " Hello there. "}
    )
    await bridge._handle_event(
        {
            "type": "conversation.item.input_audio_transcription.completed",
            "transcript": "I need help",
        }
    )

    assert bot_texts == ["Hello there."]
    assert caller_texts == ["I need help"]
