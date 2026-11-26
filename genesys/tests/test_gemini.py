import asyncio
import base64
import json
import struct

import pytest
import websockets

from app.ai.gemini import GeminiLiveBridge
from app.config import Settings

RATE_24K = 24000


def make_bridge(**settings_overrides):
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

    settings = Settings(gemini_api_key="test-key", **settings_overrides)
    bridge = GeminiLiveBridge(
        settings=settings,
        on_audio=on_audio,
        on_barge_in=on_barge_in,
        on_bot_text=on_bot_text,
        on_caller_text=on_caller_text,
    )
    return bridge, audio, barge_ins, bot_texts, caller_texts


def audio_part(pcm: bytes, rate: int = RATE_24K) -> dict:
    return {
        "inlineData": {
            "mimeType": f"audio/pcm;rate={rate}",
            "data": base64.b64encode(pcm).decode("ascii"),
        }
    }


def silence_pcm(samples: int) -> bytes:
    return struct.pack(f"<{samples}h", *([0] * samples))


async def capture_sends(bridge):
    sent = []

    async def fake_send(payload: dict) -> None:
        sent.append(payload)

    bridge._send = fake_send
    return sent


def test_provider_selection_and_readiness():
    # Use an explicit env file path to avoid picking up the developer's .env.
    base = dict(_env_file="__missing__.env")

    default = Settings(**base, ai_provider="openai", openai_api_key="", gemini_api_key="")
    assert default.provider == "openai"
    assert default.ai_ready is False

    gemini = Settings(**base, ai_provider="gemini", gemini_api_key="AIza-test", openai_api_key="")
    assert gemini.provider == "gemini"
    assert gemini.ai_ready is True
    assert gemini.openai_ready is False

    alias = Settings(**base, ai_provider="google")
    assert alias.provider == "gemini"

    openai = Settings(**base, ai_provider="openai", openai_api_key="sk-test", gemini_api_key="")
    assert openai.provider == "openai"
    assert openai.ai_ready is True

    typhoon = Settings(**base, ai_provider="typhoon", typhoon_base_url="http://127.0.0.1:8001/v1")
    assert typhoon.provider == "typhoon"
    assert typhoon.ai_ready is True
    assert typhoon.typhoon_ready is True

    typhoon_alias = Settings(**base, ai_provider="vllm")
    assert typhoon_alias.provider == "typhoon"


@pytest.mark.asyncio
async def test_setup_message_is_audio_only_and_prefixed():
    bridge, *_ = make_bridge()

    setup = bridge._setup_payload(resume=False)["setup"]

    assert setup["model"] == "models/gemini-3.8-live"
    generation = setup["generationConfig"]
    assert generation["responseModalities"] == ["AUDIO"]
    assert generation["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"] == {
        "voiceName": "Kore"
    }
    assert "speechConfig" not in setup
    assert setup["systemInstruction"]["parts"]
    assert setup["inputAudioTranscription"] == {}
    assert setup["outputAudioTranscription"] == {}
    assert setup["sessionResumption"] == {}
    assert "contextWindowCompression" in setup
    assert setup["realtimeInputConfig"]["automaticActivityDetection"] == {
        "prefixPaddingMs": 300,
        "silenceDurationMs": 600,
    }


@pytest.mark.asyncio
async def test_setup_reuses_existing_models_prefix_and_resume_handle():
    bridge, *_ = make_bridge(gemini_model="models/gemini-3.1-flash-live-preview")
    bridge._resume_handle = "resume-123"

    setup = bridge._setup_payload(resume=True)["setup"]

    assert setup["model"] == "models/gemini-3.1-flash-live-preview"
    assert setup["sessionResumption"] == {"handle": "resume-123"}


@pytest.mark.asyncio
async def test_setup_can_disable_transcription_and_resumption():
    bridge, *_ = make_bridge(
        gemini_enable_transcription=False, gemini_session_resumption=False
    )

    setup = bridge._setup_payload(resume=False)["setup"]

    assert "inputAudioTranscription" not in setup
    assert "outputAudioTranscription" not in setup
    assert "sessionResumption" not in setup


@pytest.mark.asyncio
async def test_send_audio_upsamples_ulaw_8k_to_pcm16_16k():
    bridge, *_ = make_bridge()
    sent = await capture_sends(bridge)
    bridge._ws = object()

    await bridge.send_audio(b"\xff" * 160)  # 20 ms of PCMU silence

    payload = sent[0]["realtimeInput"]["audio"]
    assert payload["mimeType"] == "audio/pcm;rate=16000"
    pcm = base64.b64decode(payload["data"])
    assert len(pcm) == 160 * 2 * 2  # 160 samples @8k -> 320 samples @16k


@pytest.mark.asyncio
async def test_model_audio_24k_is_downsampled_to_ulaw_8k():
    bridge, audio, barge_ins, *_ = make_bridge()

    await bridge._handle_server_content(
        {
            "modelTurn": {
                "parts": [audio_part(silence_pcm(480))]  # 20 ms @ 24 kHz
            }
        }
    )

    assert audio == [b"\xff" * 160]
    assert bridge._playing is True
    assert barge_ins == []


@pytest.mark.asyncio
async def test_interrupted_triggers_barge_in_only_while_playing():
    bridge, audio, barge_ins, *_ = make_bridge()

    # Nothing playing yet -> no barge-in event.
    await bridge._handle_server_content({"interrupted": True})
    assert barge_ins == []

    await bridge._handle_server_content(
        {"modelTurn": {"parts": [audio_part(silence_pcm(480))]}}
    )
    await bridge._handle_server_content({"interrupted": True})

    assert barge_ins == [True]
    assert bridge._playing is False
    assert len(audio) == 1


@pytest.mark.asyncio
async def test_turn_complete_resets_playing_state():
    bridge, *_ = make_bridge()

    await bridge._handle_server_content(
        {"modelTurn": {"parts": [audio_part(silence_pcm(480))]}}
    )
    await bridge._handle_server_content({"turnComplete": True})

    assert bridge._playing is False


@pytest.mark.asyncio
async def test_transcripts_are_flushed_on_turn_complete():
    bridge, _, _, bot_texts, caller_texts = make_bridge()

    await bridge._handle_server_content(
        {
            "outputTranscription": {"text": "Hello"},
            "inputTranscription": {"text": "I need"},
        }
    )
    await bridge._handle_server_content(
        {
            "outputTranscription": {"text": " there"},
            "inputTranscription": {"text": " help"},
        }
    )
    # Nothing is emitted until the turn is complete.
    assert bot_texts == []
    assert caller_texts == []

    await bridge._handle_server_content({"turnComplete": True})

    assert bot_texts == ["Hello there"]
    assert caller_texts == ["I need help"]


@pytest.mark.asyncio
async def test_transcripts_are_flushed_on_generation_complete():
    bridge, _, _, bot_texts, caller_texts = make_bridge()

    await bridge._handle_server_content(
        {"outputTranscription": {"text": "สวัสดีค่ะ"}}
    )
    await bridge._handle_server_content(
        {"inputTranscription": {"text": "สวัสดีครับ"}}
    )
    assert bot_texts == []

    # Native-audio models end a turn with generationComplete, not turnComplete.
    await bridge._handle_server_content({"generationComplete": True})

    assert bot_texts == ["สวัสดีค่ะ"]
    assert caller_texts == ["สวัสดีครับ"]


@pytest.mark.asyncio
async def test_text_parts_are_used_when_no_output_transcription():
    bridge, _, _, bot_texts, _ = make_bridge()

    await bridge._handle_server_content(
        {"modelTurn": {"parts": [{"text": "Hello"}]}}
    )
    await bridge._handle_server_content(
        {"modelTurn": {"parts": [{"text": " there"}]}}
    )
    await bridge._handle_server_content({"turnComplete": True})

    assert bot_texts == ["Hello there"]


@pytest.mark.asyncio
async def test_cumulative_transcription_snapshots_are_deduplicated():
    bridge, _, _, bot_texts, _ = make_bridge()

    await bridge._handle_server_content(
        {"outputTranscription": {"text": "Hello"}}
    )
    await bridge._handle_server_content(
        {"outputTranscription": {"text": "Hello there"}}
    )
    await bridge._handle_server_content({"turnComplete": True})

    assert bot_texts == ["Hello there"]


@pytest.mark.asyncio
async def test_session_resumption_handle_is_stored():
    bridge, *_ = make_bridge()

    await bridge._handle_message(
        {"sessionResumptionUpdate": {"newHandle": "h-1", "resumable": True}}
    )
    assert bridge._resume_handle == "h-1"

    # A non-resumable update must not wipe the last good handle.
    await bridge._handle_message(
        {"sessionResumptionUpdate": {"newHandle": "", "resumable": False}}
    )
    assert bridge._resume_handle == "h-1"


@pytest.mark.asyncio
async def test_setup_complete_sets_the_readiness_event():
    bridge, *_ = make_bridge()

    assert bridge._setup_done.is_set() is False
    await bridge._handle_message({"setupComplete": {}})
    assert bridge._setup_done.is_set() is True


@pytest.mark.asyncio
async def test_greeting_uses_client_content_with_turn_complete():
    bridge, *_ = make_bridge()
    sent = await capture_sends(bridge)

    await bridge.request_greeting()

    content = sent[0]["clientContent"]
    assert content["turnComplete"] is True
    assert content["turns"][0]["role"] == "user"
    assert content["turns"][0]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_pause_sends_audio_stream_end():
    bridge, *_ = make_bridge()
    sent = await capture_sends(bridge)
    bridge._ws = object()

    await bridge.pause()

    assert sent == [{"realtimeInput": {"audioStreamEnd": True}}]


@pytest.mark.asyncio
async def test_connect_sends_setup_and_waits_for_setup_complete():
    setups = []
    connected = asyncio.Event()

    async def handler(ws):
        setups.append(json.loads(await ws.recv()))
        connected.set()
        await ws.send(json.dumps({"setupComplete": {}}))
        try:
            async for _ in ws:
                pass
        except websockets.ConnectionClosed:
            pass

    server = await websockets.serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        bridge, *_ = make_bridge(
            gemini_live_url=f"ws://127.0.0.1:{port}/live"
        )
        await bridge.connect()

        await asyncio.wait_for(connected.wait(), timeout=5)
        assert setups[0]["setup"]["model"] == "models/gemini-3.8-live"
        assert bridge.connected is True
    finally:
        await bridge.stop()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_reader_reconnects_with_resume_handle():
    setups = []
    second_connection = asyncio.Event()

    async def handler(ws):
        setups.append(json.loads(await ws.recv()))
        await ws.send(json.dumps({"setupComplete": {}}))
        if len(setups) == 1:
            await ws.send(
                json.dumps(
                    {
                        "sessionResumptionUpdate": {
                            "newHandle": "h-1",
                            "resumable": True,
                        }
                    }
                )
            )
            await ws.close()
            return
        second_connection.set()
        try:
            async for _ in ws:
                pass
        except websockets.ConnectionClosed:
            pass

    server = await websockets.serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        bridge, *_ = make_bridge(
            gemini_live_url=f"ws://127.0.0.1:{port}/live",
            gemini_reconnect_attempts=1,
        )
        await bridge.connect()
        await bridge.start_reader()

        await asyncio.wait_for(second_connection.wait(), timeout=5)
        assert setups[1]["setup"]["sessionResumption"] == {"handle": "h-1"}
    finally:
        await bridge.stop()
        server.close()
        await server.wait_closed()
