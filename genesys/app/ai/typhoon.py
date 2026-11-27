"""Typhoon (self-hosted vLLM) cascade bridge.

This provider connects Genesys AudioHook audio to a text-only LLM served behind
an OpenAI-compatible Chat Completions API (e.g. vLLM running Typhoon).

Because chat-completions is text-only, the bridge performs a cascade:

    Genesys PCMU 8kHz -> VAD/buffer -> STT -> Typhoon LLM -> TTS -> PCMU 8kHz

STT and TTS are configurable.  TTS supports ``edge_tts`` (like
BKK-CivicVoice-AI) and OpenAI-compatible ``/v1/audio/speech`` endpoints.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import math
import struct
import time
import wave
from typing import Awaitable, Callable, Optional

import httpx

from ..config import Settings
from ..data_context import load_data_context
from .audio import pcm16_to_ulaw, resample_pcm16, ulaw_to_pcm16

AudioCallback = Callable[[bytes], Awaitable[None]]
AsyncCallback = Callable[[], Awaitable[None]]
TextCallback = Callable[[str], Awaitable[None]]


def _pcm16_rms(pcm16: bytes) -> int:
    if not pcm16:
        return 0
    n = len(pcm16) // 2
    if n <= 0:
        return 0
    samples = struct.unpack(f"<{n}h", pcm16[: n * 2])
    # Mean square; avoid float-heavy path for typical frame sizes.
    acc = 0
    for s in samples:
        acc += s * s
    return int(math.sqrt(acc / n))


def _wav_bytes(pcm16: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16)
    return buf.getvalue()


def _pcm_to_pcm16(pcm: bytes, width: int) -> bytes:
    if width == 2:
        return pcm
    if width == 1:
        # Unsigned 8-bit PCM -> signed 16-bit
        samples = struct.unpack(f"{len(pcm)}B", pcm)
        return struct.pack(f"<{len(samples)}h", *[(s - 128) << 8 for s in samples])
    if width == 3:
        out = bytearray(len(pcm) // 3 * 2)
        j = 0
        for i in range(0, len(pcm) - 2, 3):
            v = int.from_bytes(pcm[i : i + 3], "little", signed=True)
            struct.pack_into("<h", out, j, max(-32768, min(32767, v >> 8)))
            j += 2
        return bytes(out[:j])
    if width == 4:
        n = len(pcm) // 4
        samples = struct.unpack(f"<{n}i", pcm[: n * 4])
        return struct.pack(f"<{n}h", *[max(-32768, min(32767, s >> 16)) for s in samples])
    raise RuntimeError(f"unsupported PCM width: {width}")


def _stereo_to_mono_pcm16(pcm: bytes) -> bytes:
    n = len(pcm) // 4  # 2 channels * 2 bytes
    if n <= 0:
        return pcm
    samples = struct.unpack(f"<{n * 2}h", pcm[: n * 4])
    mono = [int((samples[i] + samples[i + 1]) / 2) for i in range(0, len(samples), 2)]
    return struct.pack(f"<{len(mono)}h", *mono)


def _decode_audio_to_pcm16(data: bytes, content_type: str = "") -> tuple[bytes, int]:
    """Decode WAV/PCM/MP3 audio bytes to PCM16 and sample rate."""

    ct = (content_type or "").lower()
    head = data[:16]

    # WAV / RIFF
    if head.startswith(b"RIFF") or "wav" in ct:
        with wave.open(io.BytesIO(data), "rb") as wf:
            rate = wf.getframerate()
            channels = wf.getnchannels()
            width = wf.getsampwidth()
            pcm = wf.readframes(wf.getnframes())
        pcm = _pcm_to_pcm16(pcm, width)
        if channels > 1:
            pcm = _stereo_to_mono_pcm16(pcm)
        return pcm, rate

    # Raw PCM16 (some OpenAI-compatible servers)
    if "pcm" in ct or "octet-stream" in ct or "raw" in ct:
        return data, 24000

    # MP3 / other - try miniaudio
    try:
        import miniaudio

        decoded = miniaudio.decode(
            data,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=24000,
        )
        pcm = bytes(decoded.samples)
        return pcm, decoded.sample_rate
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"unsupported TTS audio format: {content_type!r}") from exc


class TyphoonVLLMBridge:
    def __init__(
        self,
        settings: Settings,
        on_audio: AudioCallback,
        on_barge_in: AsyncCallback,
        on_bot_text: TextCallback,
        on_caller_text: TextCallback,
    ) -> None:
        self._settings = settings
        self._on_audio = on_audio
        self._on_barge_in = on_barge_in
        self._on_bot_text = on_bot_text
        self._on_caller_text = on_caller_text
        self._log = logging.getLogger("typhoon.vllm")

        self._http: Optional[httpx.AsyncClient] = None
        self._worker: Optional[asyncio.Task] = None
        self._turns: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._stopped = False
        self._speaking = False
        self._speak_started = 0.0
        self._response_task: Optional[asyncio.Task] = None

        # VAD state
        self._utterance = bytearray()
        self._speech_started = False
        self._silence_ms = 0
        self._speech_ms = 0

        instructions = settings.typhoon_instructions
        data_ctx = load_data_context(settings)
        if data_ctx:
            instructions = f"{instructions}\n\n{data_ctx}"
        self._messages: list[dict[str, str]] = [
            {"role": "system", "content": instructions}
        ]

    @property
    def connected(self) -> bool:
        return self._http is not None and not self._stopped

    async def connect(self) -> None:
        timeout = httpx.Timeout(self._settings.typhoon_connect_timeout, connect=5.0)
        self._http = httpx.AsyncClient(timeout=timeout)
        self._log.info(
            "Typhoon bridge ready (llm=%s model=%s stt=%s tts=%s)",
            self._settings.typhoon_base_url,
            self._settings.typhoon_model,
            self._settings.typhoon_stt_base_url,
            self._settings.typhoon_tts_provider,
        )

    async def start_reader(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run_worker(), name="typhoon-worker")

    async def stop(self) -> None:
        self._stopped = True
        await self._cancel_response()
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except (asyncio.CancelledError, Exception):
                pass
            self._worker = None
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def pause(self) -> None:
        self._reset_utterance()
        await self._cancel_response()

    async def commit_audio(self) -> None:
        # No-op: VAD commits automatically.
        return

    async def send_audio(self, ulaw_bytes: bytes) -> None:
        if self._stopped or not ulaw_bytes:
            return

        pcm = ulaw_to_pcm16(ulaw_bytes)
        rms = _pcm16_rms(pcm)
        frame_ms = max(int(len(ulaw_bytes) / 8), 20)  # 8kHz ulaw = 1 byte/sample
        threshold = max(int(self._settings.typhoon_vad_energy_threshold), 0)
        is_speech = rms >= threshold

        if self._speaking and is_speech:
            # Ignore early echo/noise during bot greeting/start of speech.
            if (time.monotonic() - self._speak_started) >= 4.0:
                # Caller barge-in.
                self._log.info("caller barge-in detected (rms=%s)", rms)
                self._speaking = False
                await self._cancel_response()
                await self._on_barge_in()

        if is_speech:
            self._speech_started = True
            self._silence_ms = 0
            self._speech_ms += frame_ms
            self._utterance.extend(pcm)
        elif self._speech_started:
            self._silence_ms += frame_ms
            self._utterance.extend(pcm)
            silence_limit = max(int(self._settings.typhoon_vad_silence_ms), 200)
            max_ms = int(max(float(self._settings.typhoon_max_utterance_s), 1.0) * 1000)
            if self._silence_ms >= silence_limit or self._speech_ms >= max_ms:
                await self._flush_utterance()

    async def _flush_utterance(self) -> None:
        if not self._utterance:
            self._reset_utterance()
            return
        # Ignore very short/noisy blips.
        if self._speech_ms < 250:
            self._reset_utterance()
            return
        pcm = bytes(self._utterance)
        self._reset_utterance()
        await self._turns.put(pcm)

    def _reset_utterance(self) -> None:
        self._utterance.clear()
        self._speech_started = False
        self._silence_ms = 0
        self._speech_ms = 0

    async def request_greeting(self) -> None:
        text = (self._settings.greeting_instructions or "").strip()
        if not text:
            return
        # Speak the configured greeting verbatim for deterministic output.
        await self._turns.put(("__greeting__", text))  # sentinel tuple

    async def _run_worker(self) -> None:
        try:
            while not self._stopped:
                item = await self._turns.get()
                if item is None or self._stopped:
                    return
                if isinstance(item, tuple) and item[0] == "__greeting__":
                    await self._handle_greeting(item[1])
                else:
                    await self._handle_utterance(item)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._log.exception("typhoon worker crashed")

    async def _handle_greeting(self, text: str) -> None:
        self._response_task = asyncio.current_task()
        try:
            reply = (text or "").strip()
            if reply and not self._stopped:
                await self._on_bot_text(reply)
                await self._speak(reply)
        finally:
            self._response_task = None

    async def _handle_utterance(self, pcm16_8k: bytes) -> None:
        self._response_task = asyncio.current_task()
        try:
            text = await self._transcribe(pcm16_8k)
            text = (text or "").strip()
            if not text or self._stopped:
                return
            self._log.info("caller: %s", text)
            await self._on_caller_text(text)
            reply = await self._llm_reply(text, add_user=True)
            if not reply or self._stopped:
                return
            self._log.info("bot: %s", reply)
            await self._on_bot_text(reply)
            await self._speak(reply)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._log.exception("failed to handle caller utterance")
        finally:
            self._response_task = None

    async def _cancel_response(self) -> None:
        task = self._response_task
        self._response_task = None
        self._speaking = False
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def _transcribe(self, pcm16_8k: bytes) -> str:
        if self._http is None:
            return ""
        # Upsample to 16k for better STT.
        pcm16_16k = resample_pcm16(pcm16_8k, 8000, 16000)
        wav = _wav_bytes(pcm16_16k, 16000)
        url = self._settings.typhoon_stt_base_url.rstrip("/") + "/audio/transcriptions"
        headers = {}
        if self._settings.typhoon_stt_api_key.strip():
            headers["Authorization"] = f"Bearer {self._settings.typhoon_stt_api_key.strip()}"
        data = {"model": self._settings.typhoon_stt_model}
        lang = (self._settings.typhoon_stt_language or "").strip()
        if lang:
            data["language"] = lang
        files = {"file": ("audio.wav", wav, "audio/wav")}
        resp = await self._http.post(url, headers=headers, data=data, files=files)
        resp.raise_for_status()
        body = resp.json()
        return (body.get("text") or "").strip()

    async def _llm_reply(self, user_text: str, *, add_user: bool) -> str:
        if self._http is None:
            return ""

        voicebot_url = (getattr(self._settings, "typhoon_voicebot_url", "") or "").strip()
        if add_user and voicebot_url:
            self._messages.append({"role": "user", "content": user_text})
            try:
                resp = await self._http.post(
                    voicebot_url,
                    json={"message": user_text, "language": "th"},
                )
                resp.raise_for_status()
                body = resp.json()
                reply = (
                    body.get("reply_text")
                    or body.get("text")
                    or body.get("reply")
                    or body.get("message")
                    or ""
                ).strip()
            except Exception:
                self._log.exception("voicebot converse failed, falling back to LLM")
                reply = await self._llm_chat(self._messages)
            if reply:
                self._messages.append({"role": "assistant", "content": reply})
                if len(self._messages) > 21:
                    self._messages = [self._messages[0]] + self._messages[-20:]
            return reply

        if add_user:
            self._messages.append({"role": "user", "content": user_text})
            messages = self._messages
        else:
            messages = self._messages + [{"role": "user", "content": user_text}]

        reply = await self._llm_chat(messages)
        if add_user and reply:
            self._messages.append({"role": "assistant", "content": reply})
            if len(self._messages) > 21:
                self._messages = [self._messages[0]] + self._messages[-20:]
        return reply

    async def _llm_chat(self, messages: list[dict[str, str]]) -> str:
        url = self._settings.typhoon_base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._settings.typhoon_api_key.strip():
            headers["Authorization"] = f"Bearer {self._settings.typhoon_api_key.strip()}"
        payload = {
            "model": self._settings.typhoon_model,
            "messages": messages,
            "max_tokens": max(int(self._settings.typhoon_max_tokens), 1),
            "temperature": float(self._settings.typhoon_temperature),
        }
        resp = await self._http.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        body = resp.json()
        choices = body.get("choices") or []
        if not choices:
            return ""
        content = ((choices[0] or {}).get("message") or {}).get("content") or ""
        return content.strip()

    async def _speak(self, text: str) -> None:
        if self._stopped or not text.strip():
            return
        self._speaking = True
        self._speak_started = time.monotonic()
        try:
            pcm16, rate = await self._synthesize(text)
            if self._stopped or not self._speaking:
                return
            if rate != 8000:
                pcm16 = resample_pcm16(pcm16, rate, 8000)
            ulaw = pcm16_to_ulaw(pcm16)
            # Chunk into ~200ms frames to allow barge-in checks.
            frame = 1600  # 200ms at 8kHz ulaw
            for i in range(0, len(ulaw), frame):
                if self._stopped or not self._speaking:
                    break
                await self._on_audio(ulaw[i : i + frame])
        finally:
            self._speaking = False

    async def _synthesize(self, text: str) -> tuple[bytes, int]:
        provider = (self._settings.typhoon_tts_provider or "edge_tts").strip().lower()
        if provider == "edge_tts":
            return await self._tts_edge(text)
        if provider == "gemini":
            return await self._tts_gemini(text)
        return await self._tts_openai(text)

    async def _tts_openai(self, text: str) -> tuple[bytes, int]:
        if self._http is None:
            return b"", 8000
        url = self._settings.typhoon_tts_base_url.rstrip("/") + "/audio/speech"
        headers = {"Content-Type": "application/json"}
        if self._settings.typhoon_tts_api_key.strip():
            headers["Authorization"] = f"Bearer {self._settings.typhoon_tts_api_key.strip()}"
        payload = {
            "model": self._settings.typhoon_tts_model,
            "input": text,
            "voice": self._settings.typhoon_tts_voice,
            "response_format": "wav",
            "speed": float(self._settings.typhoon_tts_speed),
        }
        resp = await self._http.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return _decode_audio_to_pcm16(resp.content, resp.headers.get("content-type", ""))

    async def _tts_gemini(self, text: str) -> tuple[bytes, int]:
        if self._http is None:
            return b"", 8000
        api_key = (getattr(self._settings, "gemini_api_key", "") or "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for TYPHOON_TTS_PROVIDER=gemini")

        model = (self._settings.typhoon_tts_model or "").strip() or "gemini-2.5-flash-preview-tts"
        voice = (self._settings.typhoon_tts_voice or "").strip() or "Kore"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        payload = {
            "contents": [{"parts": [{"text": f"Read aloud the following text exactly as written:\n{text}"}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
                },
            },
        }
        resp = await self._http.post(url, headers=headers, json=payload, timeout=30.0)
        resp.raise_for_status()
        body = resp.json()
        candidates = body.get("candidates") or []
        for cand in candidates:
            content = (cand or {}).get("content") or {}
            for part in content.get("parts") or []:
                inline = (part or {}).get("inlineData") or (part or {}).get("inline_data") or {}
                data_b64 = inline.get("data")
                if not data_b64:
                    continue
                mime = inline.get("mimeType") or inline.get("mime_type") or "audio/L16;codec=pcm;rate=24000"
                raw = base64.b64decode(data_b64)
                # Gemini TTS commonly returns raw PCM (L16). Add WAV header handling fallback.
                if "pcm" in mime.lower() and not raw.startswith(b"RIFF"):
                    # audio/L16;codec=pcm;rate=24000
                    rate = 24000
                    for token in mime.replace(";", " ").split():
                        if token.startswith("rate="):
                            try:
                                rate = int(token.split("=", 1)[1])
                            except Exception:
                                pass
                    return raw, rate
                return _decode_audio_to_pcm16(raw, mime)
        raise RuntimeError("Gemini TTS returned no audio data")

    async def _tts_edge(self, text: str) -> tuple[bytes, int]:
        try:
            import edge_tts
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "edge-tts is not installed. pip install edge-tts or set TYPHOON_TTS_PROVIDER=openai"
            ) from exc

        voice = self._settings.typhoon_tts_voice or "th-TH-PremwadeeNeural"
        communicate = edge_tts.Communicate(text, voice)
        chunks = bytearray()
        async for chunk in communicate.stream():
            if self._stopped or not self._speaking:
                break
            if chunk.get("type") == "audio":
                chunks.extend(chunk.get("data") or b"")
        if not chunks:
            return b"", 8000
        return _decode_audio_to_pcm16(bytes(chunks), "audio/mpeg")
