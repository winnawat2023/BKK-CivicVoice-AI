"""OpenAI Realtime API client used as the "brain" of the voice bot.

The bridge is deliberately transport-only: it converts between the Genesys
AudioHook audio frames and OpenAI Realtime events and surfaces a few callbacks
so the AudioHook session can react (play audio, barge-in, transcript events).

Audio path (default, ``OPENAI_AUDIO_FORMAT=pcmu``):
    Genesys PCMU 8kHz binary frame  ->  input_audio_buffer.append (base64)
    response.output_audio.delta     ->  Genesys binary frame (PCMU 8kHz)

No resampling or transcoding happens in that mode.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Awaitable, Callable, Optional

import websockets

from ..config import Settings
from .audio import pcm16_to_ulaw, resample_pcm16, ulaw_to_pcm16

AudioCallback = Callable[[bytes], Awaitable[None]]
AsyncCallback = Callable[[], Awaitable[None]]
TextCallback = Callable[[str], Awaitable[None]]


class RealtimeBridge:
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
        self._log = logging.getLogger("openai.realtime")

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._send_lock = asyncio.Lock()
        self._stopped = False
        self._playing = False
        # While True we drop model audio chunks that belong to a response the
        # caller has already barged in on.
        self._muting = False

    # -- lifecycle ----------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._stopped

    async def connect(self) -> None:
        """Open the OpenAI Realtime WebSocket and configure the session."""

        url = f"{self._settings.openai_realtime_url}?model={self._settings.openai_model}"
        headers = {"Authorization": f"Bearer {self._settings.openai_api_key}"}
        self._log.info("connecting to OpenAI Realtime (%s)", self._settings.openai_model)
        # ``websockets`` < 14 exposes the legacy client at the top level, which
        # takes ``extra_headers`` (the newer asyncio client renamed it to
        # ``additional_headers``).
        self._ws = await websockets.connect(
            url,
            extra_headers=headers,
            max_size=None,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=self._settings.openai_connect_timeout,
        )
        await self._send_session_update()

    async def start_reader(self) -> None:
        if self._reader_task is None:
            self._reader_task = asyncio.create_task(
                self._reader_loop(), name="openai-realtime-reader"
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
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._log.info("OpenAI Realtime session closed")

    # -- outbound (Genesys -> OpenAI) --------------------------------------
    async def send_audio(self, ulaw_bytes: bytes) -> None:
        """Forward caller audio to the Realtime input buffer."""

        if not ulaw_bytes or self._ws is None:
            return
        if self._settings.normalized_audio_format == "pcm":
            pcm_8k = ulaw_to_pcm16(ulaw_bytes)
            payload = resample_pcm16(pcm_8k, 8000, 24000)
        else:
            payload = ulaw_bytes
        await self._send(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(payload).decode("ascii"),
            }
        )

    async def request_greeting(self) -> None:
        """Ask the model to speak first (used right after ``opened``)."""

        await self._send(
            {
                "type": "response.create",
                "response": {"instructions": self._settings.greeting_instructions},
            }
        )

    async def cancel_response(self) -> None:
        await self._send({"type": "response.cancel"})

    async def pause(self) -> None:
        """The client stopped sending audio.

        OpenAI's server VAD ends the turn on its own, so there is nothing to
        send; the method exists to keep the bridge interface uniform.
        """

        self._log.debug("pause is a no-op for OpenAI Realtime")

    # -- session configuration ---------------------------------------------
    async def _send_session_update(self) -> None:
        if self._settings.normalized_audio_format == "pcm":
            input_format = {"type": "audio/pcm", "rate": 24000}
            output_format = {"type": "audio/pcm", "rate": 24000}
        else:
            input_format = {"type": "audio/pcmu"}
            output_format = {"type": "audio/pcmu"}

        audio_input: dict = {
            "format": input_format,
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
                "create_response": True,
                "interrupt_response": True,
            },
        }
        if self._settings.openai_transcription_model:
            audio_input["transcription"] = {
                "model": self._settings.openai_transcription_model
            }

        session = {
            "type": "realtime",
            "output_modalities": ["audio"],
            "instructions": self._settings.openai_instructions,
            "audio": {
                "input": audio_input,
                "output": {
                    "format": output_format,
                    "voice": self._settings.openai_voice,
                },
            },
        }
        await self._send({"type": "session.update", "session": session})

    # -- inbound (OpenAI -> Genesys) ---------------------------------------
    async def _reader_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    event = json.loads(raw)
                except (TypeError, ValueError):
                    self._log.debug("ignoring non-JSON frame from OpenAI")
                    continue
                await self._handle_event(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._log.exception("OpenAI Realtime reader stopped unexpectedly")

    async def _handle_event(self, event: dict) -> None:
        event_type = event.get("type", "")

        if event_type in (
            "response.output_audio.delta",
            "response.audio.delta",  # beta alias
        ):
            if self._muting:
                return
            delta = event.get("delta")
            if not delta:
                return
            data = base64.b64decode(delta)
            if self._settings.normalized_audio_format == "pcm":
                pcm_8k = resample_pcm16(data, 24000, 8000)
                data = pcm16_to_ulaw(pcm_8k)
            self._playing = True
            await self._on_audio(data)
            return

        if event_type in ("response.output_audio.done", "response.audio.done", "response.done"):
            self._playing = False
            self._muting = False
            return

        if event_type in (
            "response.output_audio_transcript.done",
            "response.audio_transcript.done",
        ):
            text = (event.get("transcript") or "").strip()
            if text:
                await self._on_bot_text(text)
            return

        if event_type == "conversation.item.input_audio_transcription.completed":
            text = (event.get("transcript") or "").strip()
            if text:
                await self._on_caller_text(text)
            return

        if event_type == "input_audio_buffer.speech_started":
            # Caller started talking.  If we are currently playing, let Genesys
            # stop playback (barge-in) and drop whatever audio is still queued.
            if self._playing:
                self._muting = True
                await self._on_barge_in()
            return

        if event_type == "error":
            error = event.get("error") or {}
            self._log.error(
                "OpenAI error: %s - %s",
                error.get("type") or error.get("code"),
                error.get("message"),
            )
            return

        if event_type in (
            "session.created",
            "session.updated",
            "response.created",
            "response.output_item.added",
        ):
            self._log.debug("OpenAI event: %s", event_type)
            return

        # Everything else (text deltas, rate limits, etc.) is intentionally
        # ignored to keep the hot path small.

    # -- helpers ------------------------------------------------------------
    async def _send(self, payload: dict) -> None:
        if self._ws is None or self._stopped:
            return
        async with self._send_lock:
            try:
                await self._ws.send(json.dumps(payload))
            except Exception:
                self._log.exception("failed to send event to OpenAI")
