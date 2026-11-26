"""One AudioHook session: protocol state machine + audio/event bridging.

The class owns the WebSocket connection, validates the protocol sequence
numbers, negotiates the media format, and talks to the AI backend through
:class:`app.ai.realtime.RealtimeBridge`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Optional

from fastapi import WebSocket

from ..config import Settings
from ..transcript import build_turn_payload, emit_turn
from .messages import (
    PROTOCOL_VERSION,
    barge_in_entity,
    bot_turn_response_entity,
    choose_media,
    is_connection_probe,
    server_message,
)

STATE_CONNECTED = "connected"
STATE_OPENED = "opened"
STATE_CLOSING = "closing"
STATE_CLOSED = "closed"


class AudioSender:
    """Paces server -> client audio.

    Genesys asks servers not to send audio more often than every 200 ms and to
    keep each binary frame at or below 64,000 bytes.  Model audio arrives as
    many small deltas, so we buffer them and flush on a fixed cadence.
    """

    def __init__(
        self,
        send_bytes,
        chunk_ms: int = 200,
        max_frame_bytes: int = 64000,
    ) -> None:
        self._send_bytes = send_bytes
        self._chunk_seconds = max(chunk_ms, 1) / 1000.0
        self._max_frame = max(min(max_frame_bytes, 64000), 160)
        self._buffer = bytearray()
        self._task: Optional[asyncio.Task] = None
        self._log = logging.getLogger("audiohook.audio_sender")

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="audio-sender")

    def enqueue(self, data: bytes) -> None:
        if data:
            self._buffer.extend(data)

    def clear(self) -> None:
        self._buffer.clear()

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self._buffer.clear()

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._chunk_seconds)
                while self._buffer:
                    chunk = bytes(self._buffer[: self._max_frame])
                    del self._buffer[: self._max_frame]
                    try:
                        await self._send_bytes(chunk)
                    except Exception:
                        self._log.exception("failed to send audio frame")
                        return
                    if self._buffer:
                        # Respect the minimum spacing even when we are behind.
                        await asyncio.sleep(self._chunk_seconds)
        except asyncio.CancelledError:
            raise


class AudioHookSession:
    def __init__(
        self,
        websocket: WebSocket,
        settings: Settings,
        *,
        session_id: Optional[str] = None,
    ) -> None:
        self.ws = websocket
        self.settings = settings
        self.log = logging.getLogger("audiohook.session")

        self.session_id: Optional[str] = session_id
        self._fallback_id = str(uuid.uuid4())

        self.server_seq = 0
        self.client_seq = 0
        self.state = STATE_CONNECTED

        self.selected_media: Optional[dict[str, Any]] = None
        self.open_parameters: dict[str, Any] = {}
        self.is_probe = False
        self.client_paused = False
        self.server_paused = False

        self._send_lock = asyncio.Lock()
        self._disconnecting = False
        self._shutdown_done = False

        self._bridge = None
        self._audio_sender: Optional[AudioSender] = None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    async def run(self) -> None:
        try:
            while self.state != STATE_CLOSED:
                message = await self.ws.receive()
                kind = message.get("type")
                if kind == "websocket.disconnect":
                    self.log.info("client disconnected (code=%s)", message.get("code"))
                    break
                text = message.get("text")
                data = message.get("bytes")
                if text is not None:
                    await self._on_text(text)
                elif data is not None:
                    await self._on_binary(data)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.log.exception("session loop terminated with an error")
        finally:
            await self._shutdown()

    # ------------------------------------------------------------------
    # Inbound frames
    # ------------------------------------------------------------------
    async def _on_text(self, raw: str) -> None:
        try:
            message = json.loads(raw)
        except (TypeError, ValueError):
            await self._send_disconnect("error", "Malformed JSON message")
            return

        if message.get("version") != PROTOCOL_VERSION:
            await self._send_disconnect("error", "Unsupported protocol version")
            return

        if self.session_id is None:
            self.session_id = message.get("id")
        elif message.get("id") != self.session_id:
            await self._send_disconnect("error", "Invalid session id")
            return

        seq = message.get("seq")
        if not isinstance(seq, int) or seq != self.client_seq + 1:
            self.log.warning(
                "out-of-order client seq %r (expected %s)", seq, self.client_seq + 1
            )
            await self._send_disconnect("error", "Out-of-order sequence number")
            return

        server_seq = message.get("serverseq", 0)
        if isinstance(server_seq, int) and server_seq > self.server_seq:
            await self._send_disconnect("error", "Invalid server sequence number")
            return

        self.client_seq = seq
        handler = getattr(self, f"_handle_{message.get('type')}", None)
        if handler is None:
            self.log.debug("ignoring unsupported message type %r", message.get("type"))
            return
        await handler(message)

    async def _on_binary(self, data: bytes) -> None:
        if self.state != STATE_OPENED or self._bridge is None:
            return
        if self.client_paused:
            return
        await self._bridge.send_audio(bytes(data))

    # ------------------------------------------------------------------
    # Client message handlers
    # ------------------------------------------------------------------
    async def _handle_open(self, message: dict) -> None:
        if self.state != STATE_CONNECTED:
            await self._send_disconnect("error", "Unexpected open message")
            return

        parameters = message.get("parameters") or {}
        self.open_parameters = parameters
        self.is_probe = is_connection_probe(parameters)
        input_variables = parameters.get("inputVariables")
        if input_variables:
            self.log.info("open input variables: %s", input_variables)
        else:
            self.log.info(
                "open parameters (no inputVariables): keys=%s",
                sorted(parameters.keys()),
            )

        media = choose_media(parameters.get("media") or [])
        if media is None:
            await self._send_disconnect("error", "No supported media format offered")
            return
        self.selected_media = media

        if not self.is_probe:
            try:
                await self._start_backend()
            except Exception:
                self.log.exception("failed to start AI backend")
                await self._send_disconnect("error", "AI backend unavailable")
                return

        self.state = STATE_OPENED
        await self._send("opened", {"media": [media]})
        self.log.info(
            "session opened (probe=%s, media=%s)", self.is_probe, media
        )

        if self._bridge is not None:
            await self._bridge.start_reader()
            if self.settings.bot_greeting:
                await self._bridge.request_greeting()

    async def _handle_ping(self, message: dict) -> None:
        # Must answer immediately; the client uses it for liveness and RTT.
        await self._send("pong", {})

    async def _handle_close(self, message: dict) -> None:
        reason = (message.get("parameters") or {}).get("reason")
        self.log.info("close transaction received (reason=%s)", reason)
        self.state = STATE_CLOSING
        await self._stop_backend()
        await self._send("closed", {})
        self.state = STATE_CLOSED
        try:
            await self.ws.close(code=1000)
        except Exception:
            pass

    async def _handle_paused(self, message: dict) -> None:
        self.client_paused = True
        self.log.info("client paused the stream")
        # Gemini needs an explicit end-of-stream marker when the microphone
        # goes away so it can flush cached audio and finish the turn.
        if self._bridge is not None:
            await self._bridge.pause()

    async def _handle_resumed(self, message: dict) -> None:
        self.client_paused = False
        self.log.info("client resumed the stream")

    async def _handle_update(self, message: dict) -> None:
        language = (message.get("parameters") or {}).get("language")
        self.log.info("client updated language to %r", language)

    async def _handle_dtmf(self, message: dict) -> None:
        digit = (message.get("parameters") or {}).get("digit")
        self.log.info("DTMF digit: %s", digit)

    async def _handle_playback_started(self, message: dict) -> None:
        self.log.debug("client started playback")

    async def _handle_playback_completed(self, message: dict) -> None:
        self.log.debug("client completed playback")

    async def _handle_error(self, message: dict) -> None:
        params = message.get("parameters") or {}
        self.log.warning(
            "client reported error %s: %s", params.get("code"), params.get("message")
        )

    async def _handle_discarded(self, message: dict) -> None:
        params = message.get("parameters") or {}
        self.log.info(
            "client discarded audio (start=%s, discarded=%s)",
            params.get("start"),
            params.get("discarded"),
        )

    # ------------------------------------------------------------------
    # Backend wiring
    # ------------------------------------------------------------------
    async def _start_backend(self) -> None:
        provider = self.settings.provider
        if not self.settings.ai_ready:
            if provider == "gemini":
                key_name = "GEMINI_API_KEY"
            elif provider == "typhoon":
                key_name = "TYPHOON_BASE_URL"
            else:
                key_name = "OPENAI_API_KEY"
            self.log.warning(
                "%s is not set - running protocol-only (no AI audio)", key_name
            )
            return

        # Imported lazily so the protocol layer can be unit tested without the
        # provider SDK/websockets dependencies being importable.
        if provider == "gemini":
            from ..ai.gemini import GeminiLiveBridge

            bridge = GeminiLiveBridge(
                settings=self.settings,
                on_audio=self._on_ai_audio,
                on_barge_in=self._on_ai_barge_in,
                on_bot_text=self._on_ai_bot_text,
                on_caller_text=self._on_ai_caller_text,
            )
            connect_timeout = self.settings.gemini_connect_timeout
        elif provider == "typhoon":
            from ..ai.typhoon import TyphoonVLLMBridge

            bridge = TyphoonVLLMBridge(
                settings=self.settings,
                on_audio=self._on_ai_audio,
                on_barge_in=self._on_ai_barge_in,
                on_bot_text=self._on_ai_bot_text,
                on_caller_text=self._on_ai_caller_text,
            )
            connect_timeout = self.settings.typhoon_connect_timeout
        else:
            from ..ai.realtime import RealtimeBridge

            bridge = RealtimeBridge(
                settings=self.settings,
                on_audio=self._on_ai_audio,
                on_barge_in=self._on_ai_barge_in,
                on_bot_text=self._on_ai_bot_text,
                on_caller_text=self._on_ai_caller_text,
            )
            connect_timeout = self.settings.openai_connect_timeout

        self.log.info("connecting AI backend: %s", provider)
        await asyncio.wait_for(bridge.connect(), timeout=connect_timeout + 1.0)
        self._bridge = bridge

        self._audio_sender = AudioSender(
            self._send_binary,
            chunk_ms=self.settings.server_audio_chunk_ms,
            max_frame_bytes=self.settings.max_binary_frame_bytes,
        )
        await self._audio_sender.start()

    async def _stop_backend(self) -> None:
        if self._audio_sender is not None:
            await self._audio_sender.stop()
            self._audio_sender = None
        if self._bridge is not None:
            await self._bridge.stop()
            self._bridge = None

    # -- callbacks invoked by RealtimeBridge ---------------------------
    async def _on_ai_audio(self, data: bytes) -> None:
        if self.state != STATE_OPENED or self._audio_sender is None:
            return
        self._audio_sender.enqueue(data)

    async def _on_ai_barge_in(self) -> None:
        if self._audio_sender is not None:
            self._audio_sender.clear()
        await self._send_event([barge_in_entity()])
        self.log.info("sent barge_in event to Genesys")

    async def _on_ai_bot_text(self, text: str) -> None:
        await self._send_event([bot_turn_response_entity("match", text)])
        await self._emit_transcript("bot", text)

    async def _on_ai_caller_text(self, text: str) -> None:
        self.log.info("caller said: %s", text)
        await self._emit_transcript("caller", text)

    async def _emit_transcript(self, role: str, text: str) -> None:
        payload = build_turn_payload(
            self.open_parameters, self.session_id, role, text
        )
        await emit_turn(self.settings, payload)

    # ------------------------------------------------------------------
    # Outbound helpers
    # ------------------------------------------------------------------
    @property
    def _message_id(self) -> str:
        return self.session_id or self._fallback_id

    async def _send(self, message_type: str, parameters: dict[str, Any]) -> None:
        async with self._send_lock:
            self.server_seq += 1
            message = server_message(
                self._message_id,
                message_type,
                self.server_seq,
                self.client_seq,
                parameters,
            )
            try:
                await self.ws.send_text(
                    json.dumps(message, separators=(",", ":"))
                )
            except Exception:
                self.log.exception("failed to send %s message", message_type)

    async def _send_binary(self, data: bytes) -> None:
        if self.state != STATE_OPENED:
            return
        async with self._send_lock:
            try:
                await self.ws.send_bytes(data)
            except Exception:
                self.log.exception("failed to send binary audio frame")

    async def _send_event(self, entities: list[dict[str, Any]]) -> None:
        if self.state not in (STATE_OPENED, STATE_CLOSING):
            return
        await self._send("event", {"entities": entities})

    async def _send_disconnect(self, reason: str, info: str = "") -> None:
        if self._disconnecting or self.state in (STATE_CLOSING, STATE_CLOSED):
            return
        self._disconnecting = True
        self.log.warning("sending disconnect (reason=%s, info=%s)", reason, info)
        parameters: dict[str, Any] = {"reason": reason}
        if info:
            parameters["info"] = info
        await self._send("disconnect", parameters)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    async def _shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        await self._stop_backend()
