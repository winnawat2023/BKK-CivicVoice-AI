"""Google Gemini Live API client used as the "brain" of the voice bot.

The bridge speaks the raw ``BidiGenerateContent`` WebSocket protocol
(``v1beta``) and exposes the same tiny interface as
:class:`app.ai.realtime.RealtimeBridge`, so the AudioHook session can swap
providers with a single setting.

Audio path (Gemini Live is PCM16 only):

    Genesys PCMU 8 kHz  -> decode -> PCM16 8k -> resample 16k -> realtimeInput
    serverContent.modelTurn.inlineData (PCM16 24k) -> resample 8k -> PCMU

Unlike OpenAI the server owns voice activity detection: it sends
``serverContent.interrupted`` when the caller barges in, and
``serverContent.turnComplete`` when the turn (and playback) is finished.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from typing import Awaitable, Callable, Optional

import websockets

from ..config import Settings
from ..data_context import load_data_context
from .audio import pcm16_to_ulaw, resample_pcm16, ulaw_to_pcm16

AudioCallback = Callable[[bytes], Awaitable[None]]
AsyncCallback = Callable[[], Awaitable[None]]
TextCallback = Callable[[str], Awaitable[None]]

_RATE_RE = re.compile(r"rate\s*=\s*(\d+)", re.IGNORECASE)
_DEFAULT_OUTPUT_RATE = 24000


def _audio_rate(mime_type: str, default: int = _DEFAULT_OUTPUT_RATE) -> int:
    """Extract the sample rate from ``audio/pcm;rate=24000``."""

    match = _RATE_RE.search(mime_type or "")
    if match:
        return int(match.group(1))
    return default


def _append_transcript(parts: list[str], chunk: str) -> None:
    """Append a transcription chunk, tolerating cumulative updates.

    Gemini may send transcription as deltas or as growing snapshots depending
    on the model; collapsing snapshots keeps ``bot_turn_response`` clean.
    """

    if not chunk:
        return
    if parts:
        current = "".join(parts)
        if chunk.startswith(current):
            parts[:] = [chunk]
            return
    parts.append(chunk)


class GeminiLiveBridge:
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
        self._log = logging.getLogger("gemini.live")

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._send_lock = asyncio.Lock()
        self._setup_done = asyncio.Event()
        self._stopped = False
        self._playing = False
        self._resume_handle: Optional[str] = None
        self._reconnects_left = max(settings.gemini_reconnect_attempts, 0)
        self._bot_parts: list[str] = []
        self._bot_text_parts: list[str] = []
        self._caller_parts: list[str] = []

    def _gemini_instructions(self) -> str:
        instructions = self._settings.gemini_instructions
        data_ctx = load_data_context(self._settings)
        if data_ctx:
            instructions = f"{instructions}\n\n{data_ctx}"
        return instructions

    # -- lifecycle ----------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._stopped

    async def connect(self) -> None:
        """Open the Live API socket and wait for ``setupComplete``."""

        await self._open(resume=False)

    async def _open(self, resume: bool) -> None:
        model = self._settings.gemini_model.strip()
        if not model.startswith("models/"):
            model = f"models/{model}"

        url = f"{self._settings.gemini_live_url}?key={self._settings.gemini_api_key}"
        self._log.info("connecting to Gemini Live (%s)", model)
        self._setup_done.clear()
        self._ws = await websockets.connect(
            url,
            max_size=None,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=self._settings.gemini_connect_timeout,
        )
        await self._ws.send(json.dumps(self._setup_payload(resume)))

        # The server must confirm the setup before any realtime input is sent.
        # Read the first messages here so ``setupComplete`` cannot be missed by
        # a reader that has not been started yet.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._settings.gemini_connect_timeout
        try:
            while not self._setup_done.is_set():
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise TimeoutError("timed out waiting for Gemini setupComplete")
                raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
                message = self._decode(raw)
                if message is None:
                    continue
                if "error" in message:
                    error = message.get("error") or {}
                    raise RuntimeError(
                        "Gemini setup failed: %s - %s"
                        % (
                            error.get("status") or error.get("code"),
                            error.get("message"),
                        )
                    )
                await self._handle_message(message)
        except Exception:
            await self._close_ws()
            raise

    async def start_reader(self) -> None:
        if self._reader_task is None:
            self._reader_task = asyncio.create_task(
                self._reader_loop(), name="gemini-live-reader"
            )

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reader_task = None
        await self._close_ws()
        self._log.info("Gemini Live session closed")

    async def _close_ws(self) -> None:
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    # -- outbound (Genesys -> Gemini) --------------------------------------
    async def send_audio(self, ulaw_bytes: bytes) -> None:
        """Forward caller audio as PCM16 16 kHz realtime input."""

        if not ulaw_bytes or self._ws is None or self._stopped:
            return
        rate = self._settings.gemini_input_sample_rate
        pcm_8k = ulaw_to_pcm16(ulaw_bytes)
        pcm = resample_pcm16(pcm_8k, 8000, rate) if rate != 8000 else pcm_8k
        await self._send(
            {
                "realtimeInput": {
                    "audio": {
                        "data": base64.b64encode(pcm).decode("ascii"),
                        "mimeType": f"audio/pcm;rate={rate}",
                    }
                }
            }
        )

    async def request_greeting(self) -> None:
        """Ask the model to speak first (used right after ``opened``).

        ``clientContent`` with ``turnComplete`` is the documented way to make
        the model generate a turn from text without waiting for caller audio.
        """

        greeting = (
            self._settings.gemini_greeting_prompt.strip()
            or self._settings.greeting_instructions
        )
        prompt = (
            "พูดข้อความต่อไปนี้ซ้ำตามตัวอักษรทุกคำ ห้ามเปลี่ยน ห้ามเพิ่ม ห้ามลด ห้ามแปล:\n"
            f"{greeting}"
        )
        await self._send(
            {
                "clientContent": {
                    "turns": [{"role": "user", "parts": [{"text": prompt}]}],
                    "turnComplete": True,
                }
            }
        )

    async def cancel_response(self) -> None:
        # Gemini cancels generation server-side based on VAD; there is no
        # client-side cancel message in the Live API.
        self._log.debug("cancel_response is a no-op for Gemini Live")

    async def pause(self) -> None:
        """Tell Gemini the microphone stream stopped (flush cached audio)."""

        if self._ws is None or self._stopped:
            return
        await self._send({"realtimeInput": {"audioStreamEnd": True}})

    # -- session configuration ---------------------------------------------
    def _setup_payload(self, resume: bool) -> dict:
        setup: dict = {
            "model": (
                self._settings.gemini_model
                if self._settings.gemini_model.startswith("models/")
                else f"models/{self._settings.gemini_model}"
            ),
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                # Voice selection lives under generationConfig in the raw
                # BidiGenerateContent setup message.
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": self._settings.gemini_voice
                        }
                    }
                },
            },
            "systemInstruction": {
                "parts": [{"text": self._gemini_instructions()}]
            },
            "realtimeInputConfig": {
                "automaticActivityDetection": {
                    "prefixPaddingMs": self._settings.gemini_vad_prefix_ms,
                    "silenceDurationMs": self._settings.gemini_vad_silence_ms,
                }
            },
        }

        if self._settings.gemini_enable_transcription:
            setup["inputAudioTranscription"] = {}
            setup["outputAudioTranscription"] = {}

        if self._settings.gemini_session_resumption:
            setup["sessionResumption"] = (
                {"handle": self._resume_handle}
                if resume and self._resume_handle
                else {}
            )

        if self._settings.gemini_context_window_compression:
            setup["contextWindowCompression"] = {"slidingWindow": {}}

        return {"setup": setup}

    # -- inbound (Gemini -> Genesys) ---------------------------------------
    async def _reader_loop(self) -> None:
        while not self._stopped:
            ws = self._ws
            if ws is None:
                return
            try:
                async for raw in ws:
                    message = self._decode(raw)
                    if message is not None:
                        await self._handle_message(message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._stopped:
                    return
                self._log.warning("Gemini Live connection lost: %s", exc)

            if self._stopped or not await self._reconnect():
                return

    async def _reconnect(self) -> bool:
        if not self._settings.gemini_session_resumption:
            self._log.info("Gemini Live session ended (resumption disabled)")
            return False
        if self._reconnects_left <= 0:
            self._log.warning("Gemini Live session ended; reconnect budget exhausted")
            return False

        self._reconnects_left -= 1
        self._log.info(
            "reconnecting to Gemini Live (resume=%s, attempts left=%d)",
            bool(self._resume_handle),
            self._reconnects_left,
        )
        await self._close_ws()
        try:
            await asyncio.sleep(0.5)
            await self._open(resume=bool(self._resume_handle))
        except asyncio.CancelledError:
            raise
        except Exception:
            self._log.exception("Gemini Live reconnect failed")
            return False
        return True

    @staticmethod
    def _decode(raw) -> Optional[dict]:
        if isinstance(raw, (bytes, bytearray)):
            raw = bytes(raw).decode("utf-8", "replace")
        try:
            message = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return message if isinstance(message, dict) else None

    async def _handle_message(self, message: dict) -> None:
        if "setupComplete" in message:
            self._setup_done.set()
            self._log.info(
                "Gemini Live session ready (%s)", self._settings.gemini_model
            )
            return

        if "serverContent" in message:
            await self._handle_server_content(message.get("serverContent") or {})
            return

        if "sessionResumptionUpdate" in message:
            update = message.get("sessionResumptionUpdate") or {}
            handle = update.get("newHandle")
            if update.get("resumable") and handle:
                self._resume_handle = handle
            return

        if "goAway" in message:
            time_left = (message.get("goAway") or {}).get("timeLeft", "?")
            self._log.warning(
                "Gemini Live will disconnect soon (timeLeft=%s); "
                "the session will resume automatically",
                time_left,
            )
            return

        if "toolCall" in message:
            self._log.warning(
                "Gemini requested a tool call but no tools are configured"
            )
            return

        if "usageMetadata" in message:
            usage = message.get("usageMetadata") or {}
            self._log.debug(
                "Gemini usage: prompt=%s response=%s total=%s",
                usage.get("promptTokenCount"),
                usage.get("responseTokenCount"),
                usage.get("totalTokenCount"),
            )
            return

        if "error" in message:
            error = message.get("error") or {}
            self._log.error(
                "Gemini error: %s - %s",
                error.get("status") or error.get("code"),
                error.get("message"),
            )

    async def _handle_server_content(self, content: dict) -> None:
        if content.get("interrupted"):
            # The caller spoke over the bot. Genesys must stop playback and we
            # must drop whatever is still queued in the pacer.
            was_playing = self._playing
            self._playing = False
            if was_playing:
                await self._on_barge_in()
            return

        input_text = (content.get("inputTranscription") or {}).get("text")
        if input_text:
            _append_transcript(self._caller_parts, input_text)

        output_text = (content.get("outputTranscription") or {}).get("text")
        if output_text:
            _append_transcript(self._bot_parts, output_text)

        model_turn = content.get("modelTurn") or {}
        for part in model_turn.get("parts") or []:
            text_part = part.get("text")
            if text_part and not part.get("inlineData"):
                # Some native-audio models send the spoken text as a regular
                # text part instead of ``outputTranscription``.
                _append_transcript(self._bot_text_parts, text_part)
                continue
            inline = part.get("inlineData") or {}
            encoded = inline.get("data")
            if not encoded:
                # Text parts are covered by outputTranscription.
                continue
            mime_type = inline.get("mimeType") or ""
            if mime_type and not mime_type.startswith("audio/"):
                continue
            try:
                pcm = base64.b64decode(encoded)
            except (TypeError, ValueError):
                self._log.warning("ignoring malformed model audio chunk")
                continue
            rate = _audio_rate(mime_type, self._settings.gemini_output_sample_rate)
            if rate != 8000:
                pcm = resample_pcm16(pcm, rate, 8000)
            ulaw = pcm16_to_ulaw(pcm)
            if not ulaw:
                continue
            self._playing = True
            await self._on_audio(ulaw)

        if content.get("turnComplete") or content.get("generationComplete"):
            self._playing = False
            await self._flush_transcripts()

    async def _flush_transcripts(self) -> None:
        if self._caller_parts:
            text = "".join(self._caller_parts).strip()
            self._caller_parts.clear()
            if text:
                await self._on_caller_text(text)

        if self._bot_parts:
            text = "".join(self._bot_parts).strip()
            self._bot_parts.clear()
            if text:
                await self._on_bot_text(text)
        elif self._bot_text_parts:
            text = "".join(self._bot_text_parts).strip()
            self._bot_text_parts.clear()
            if text:
                await self._on_bot_text(text)
        else:
            self._bot_text_parts.clear()

    # -- helpers ------------------------------------------------------------
    async def _send(self, payload: dict) -> None:
        ws = self._ws
        if ws is None or self._stopped:
            return
        async with self._send_lock:
            try:
                await ws.send(json.dumps(payload))
            except Exception:
                self._log.exception("failed to send message to Gemini Live")
