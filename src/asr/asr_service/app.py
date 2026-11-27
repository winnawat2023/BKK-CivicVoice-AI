"""FastAPI application: file transcription + live audio WebSocket, both feeding the CivicVoice API."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Literal, Optional

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .audio import SUPPORTED_ENCODINGS, WHISPER_RATE, decode_audio, resample
from .config import Settings
from .engine import ASRError, ModelLoadError, WhisperEngine
from .forwarder import BackendForwarder, ForwardResult
from .remote import RemoteEngine
from .streaming import UtteranceSegmenter

logger = logging.getLogger("bkk-asr")

Speaker = Literal["caller", "bot", "agent"]
MIN_SAMPLE_RATE, MAX_SAMPLE_RATE = 8000, 48000


def _default_engine(settings: Settings) -> WhisperEngine | RemoteEngine:
    if settings.engine == "remote":
        return RemoteEngine(settings)
    if settings.engine == "local":
        return WhisperEngine(settings)
    raise ValueError(f"ASR_ENGINE must be 'local' or 'remote', not {settings.engine!r}")


def create_app(
    settings: Settings | None = None,
    *,
    engine: WhisperEngine | RemoteEngine | None = None,
    backend_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = engine or _default_engine(settings)
    forwarder = BackendForwarder(settings, transport=backend_transport)
    gate = asyncio.Semaphore(settings.max_concurrency)

    async def run_transcribe(audio: Any, language: str | None):
        async with gate:  # one decode at a time per slot; the model call itself blocks, so use a thread
            return await asyncio.to_thread(engine.transcribe, audio, language)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if settings.preload:
            try:
                await asyncio.to_thread(engine.load)
            except ModelLoadError as exc:
                logger.error("Preload failed (will retry on first request): %s", exc)
        yield
        await forwarder.aclose()
        close = getattr(engine, "close", None)
        if close:
            close()

    app = FastAPI(
        title="BKK CivicVoice AI ASR Service",
        description="Faster-Whisper speech-to-text for the Bangkok 1555 hotline. Sends transcripts to the "
        "CivicVoice API (POST /api/v1/calls/{id}/segments).",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials="*" not in settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.forwarder = forwarder

    # ------------------------------------------------------------ health
    @app.get("/")
    def root():
        return {"status": "online", "service": "BKK CivicVoice AI ASR Service", "version": __version__}

    @app.get("/health")
    async def health(check_backend: bool = Query(False, description="also probe the CivicVoice API")):
        body: dict[str, Any] = {
            "status": "ok",
            "version": __version__,
            "model": settings.model,
            "model_loaded": engine.loaded,
            "device": engine.device or settings.device,
            "compute_type": engine.compute_type or settings.compute_type,
            "language": settings.language,
            "allowed_languages": list(settings.allowed_languages),
            "backend_url": settings.backend_url,
        }
        if check_backend:
            body["backend"] = await forwarder.ping()
        return body

    # ----------------------------------------------- file transcription
    @app.post("/v1/transcribe")
    async def transcribe(
        file: UploadFile = File(..., description="Audio file: wav, mp3, m4a, ogg, flac, webm..."),
        language: Optional[str] = Form(None, description="th | en | auto. Default: server setting"),
        interaction_id: Optional[str] = Form(None, description="Genesys Conversation ID; enables forwarding"),
        speaker: Speaker = Form("caller"),
        ani: Optional[str] = Form(None, description="Caller number (forwarded, never stored by this service)"),
        is_final: bool = Form(True),
        forward: Optional[bool] = Form(None, description="Send the text to the CivicVoice API (needs interaction_id)"),
    ):
        limit = settings.max_upload_mb * 1024 * 1024
        data = await file.read(limit + 1)
        if not data:
            raise HTTPException(400, "ไฟล์เสียงว่าง (empty audio file)")
        if len(data) > limit:
            raise HTTPException(413, f"ไฟล์ใหญ่เกิน {settings.max_upload_mb} MB")
        try:
            result = await run_transcribe(data, language)
        except ASRError as exc:
            logger.warning("Transcription failed: %s", exc)
            raise HTTPException(exc.status, str(exc))

        should_forward = settings.forward_default if forward is None else forward
        outcome = ForwardResult(attempted=False)
        if interaction_id and should_forward and result.text:
            outcome = await forwarder.push_segment(
                interaction_id, result.text, speaker=speaker, is_final=is_final, ani=ani
            )
        logger.info(
            "Transcribed %.1fs of audio -> %d chars (%s)", result.duration, len(result.text), result.language
        )
        return {**result.to_dict(), "interaction_id": interaction_id, "forwarded": outcome.to_dict()}

    # ------------------------------------------------- live audio stream
    @app.websocket("/v1/stream/{interaction_id}")
    async def stream(
        ws: WebSocket,
        interaction_id: str,
        encoding: str = "pcm16",
        sample_rate: int = WHISPER_RATE,
        language: Optional[str] = None,
        speaker: Speaker = "caller",
        ani: Optional[str] = None,
        forward: Optional[bool] = None,
    ):
        await ws.accept()
        if encoding not in SUPPORTED_ENCODINGS or not MIN_SAMPLE_RATE <= sample_rate <= MAX_SAMPLE_RATE:
            await ws.send_json(
                {
                    "event": "error",
                    "message": f"encoding must be one of {list(SUPPORTED_ENCODINGS)} and "
                    f"sample_rate {MIN_SAMPLE_RATE}-{MAX_SAMPLE_RATE}",
                }
            )
            await ws.close(code=1008)
            return

        should_forward = settings.forward_default if forward is None else forward
        segmenter = UtteranceSegmenter(settings)
        jobs: asyncio.Queue = asyncio.Queue()
        state = {"busy": False, "last_partial": ""}

        async def send(event: dict[str, Any]) -> None:
            try:
                await ws.send_json({"interaction_id": interaction_id, **event})
            except Exception:  # the client already left; the worker just drains
                pass

        async def worker() -> None:
            while True:
                job = await jobs.get()
                if job is None:
                    return
                kind, audio = job
                state["busy"] = True
                try:
                    result = await run_transcribe(audio, language)
                except ASRError as exc:
                    await send({"event": "error", "message": str(exc)})
                    continue
                finally:
                    state["busy"] = False
                text = result.text
                if not text:
                    continue
                if kind == "partial":
                    if text == state["last_partial"]:
                        continue
                    state["last_partial"] = text
                else:
                    state["last_partial"] = ""
                info = {"text": text, "language": result.language, "duration": round(result.duration, 3)}
                if should_forward:
                    outcome = await forwarder.push_segment(
                        interaction_id, text, speaker=speaker, is_final=(kind == "final"), ani=ani
                    )
                    info["forwarded"] = outcome.ok
                await send({"event": kind, **info})

        def queue(utterances) -> None:
            for u in utterances:
                if u.kind == "final":
                    jobs.put_nowait(("final", u.audio))
                elif not state["busy"] and jobs.empty():  # never let partials pile up behind a slow decode
                    jobs.put_nowait(("partial", u.audio))

        worker_task = asyncio.create_task(worker())
        end_call = False
        await send(
            {
                "event": "ready",
                "encoding": encoding,
                "sample_rate": sample_rate,
                "language": language or settings.language,
                "forwarding": should_forward,
                "model": settings.model,
            }
        )
        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    samples = resample(decode_audio(message["bytes"], encoding), sample_rate)
                    queue(segmenter.feed(samples))
                elif message.get("text") is not None:
                    try:
                        control = json.loads(message["text"])
                        action = control.get("action") if isinstance(control, dict) else None
                    except ValueError:
                        action, control = None, {}
                    if action == "end":
                        end_call = bool(control.get("end_call"))
                        break
                    if action == "ping":
                        await send({"event": "pong"})
                    else:
                        await send({"event": "error", "message": 'send binary audio or {"action":"end"|"ping"}'})
        except WebSocketDisconnect:
            pass
        finally:
            queue(segmenter.flush())
            jobs.put_nowait(None)
            await worker_task
            if end_call and should_forward:
                await forwarder.end_call(interaction_id)
            await send({"event": "closed", "end_call": end_call})
            try:
                await ws.close()
            except Exception:
                pass

    return app
