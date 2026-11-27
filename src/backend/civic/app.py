"""FastAPI application factory: REST endpoints + WebSocket gateway for the Agent Widget."""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .classifier import CivicClassifier
from .config import Settings
from .districts import DISTRICTS
from .hub import ConnectionHub, MONITOR_CHANNEL, SessionManager, make_event
from .llm import LLMClient, LLMError
from .pipeline import CallPipeline, spoken_ticket_id
from .rag import CivicRetriever, RagService
from .schemas import (
    TICKET_STATUSES,
    GenesysWebhookPayload,
    OutboundCallRequest,
    SegmentPayload,
    StatusUpdate,
    VoicebotChatRequest,
)
from .store import TicketStore

logger = logging.getLogger("bkk-civic-voice")

_WIDGET_DIR = Path(__file__).resolve().parents[2] / "frontend" / "widget"


class TextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class DispatchRequest(BaseModel):
    interaction_id: Optional[str] = None


def tts_url(text: str, lang: str = "th") -> str:
    return "/api/v1/tts/synthesize?" + urlencode({"text": text[:300], "lang": lang or "th"})


def create_app(
    settings: Settings | None = None,
    *,
    llm_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    llm = LLMClient(settings, transport=llm_transport) if settings.llm_enabled else None
    store = TicketStore(settings.db_path)
    hub = ConnectionHub()
    sessions = SessionManager(settings.session_ttl_s, settings.max_transcript_segments)
    classifier = CivicClassifier(llm, settings)
    rag = RagService(CivicRetriever(), llm, settings)
    pipeline = CallPipeline(settings, classifier, rag, store, sessions, hub)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await pipeline.drain()
        if llm is not None:
            await llm.aclose()
        store.close()

    app = FastAPI(
        title="BKK CivicVoice AI Middleware",
        description="Civic Contact Center API for Bangkok 1555 (Genesys Cloud CX + Thai LLM + Civic RAG)",
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
    app.state.pipeline = pipeline
    app.state.store = store
    app.state.hub = hub
    app.state.sessions = sessions
    app.state.classifier = classifier
    app.state.rag = rag
    app.state.llm = llm

    # ------------------------------------------------------------ health
    @app.get("/")
    def root():
        return {
            "status": "online",
            "service": "BKK CivicVoice AI Core Middleware",
            "version": __version__,
            "org": "ark-insights",
            "timestamp": dt.datetime.now().isoformat(),
        }

    @app.get("/api/v1/health")
    async def health(check_llm: bool = Query(False, description="also probe the vLLM server")):
        body: dict[str, Any] = {
            "status": "ok",
            "tickets": store.count(),
            "active_sessions": len(sessions),
            "widget_connections": hub.count(),
            "llm_enabled": settings.llm_enabled,
        }
        if check_llm and llm is not None:
            body["llm"] = await llm.ping()
        return body

    # --------------------------------------------- AI: understand + answer
    @app.get("/api/v1/civic/districts")
    def district_names():
        return {"districts": DISTRICTS}

    @app.post("/api/v1/civic/classify")
    async def classify(req: TextRequest):
        """Intent, category, district (1 of 50), urgency and 3-line summary for one utterance."""
        c = await classifier.classify(req.text)
        return {**c.model_dump(), "summary_th": c.summary_th}  # summary_th: design.md §3.2 output field

    @app.post("/api/v1/civic/ask")
    async def ask(req: TextRequest):
        """Civic RAG: answer a question about BKK services from the curated regulation set."""
        c = await classifier.classify(req.text)
        ans = await rag.answer(req.text, topic=c.inquiry_topic)
        return {
            "answered": ans.answered,
            "answer": ans.text,
            "via": ans.via,
            "score": ans.score,
            "transfer_to_agent": ans.transfer_to_agent,
            "sources": ans.sources,
        }

    # --------------------------------------------------- Genesys webhook
    async def _handle_webhook(payload: GenesysWebhookPayload):
        logger.info("Interaction %s: %d chars of speech", payload.interaction_id, len(payload.transcript or ""))
        result = await pipeline.process_call(payload)
        if result["reply_text"]:
            result["tts_audio_url"] = tts_url(result["reply_text"])
        return result

    app.add_api_route("/api/v1/genesys/webhook", _handle_webhook, methods=["POST"])
    app.add_api_route("/api/v1/voice/webhook", _handle_webhook, methods=["POST"], include_in_schema=False)

    # ---------------------------------------------- live call gateway (ASR)
    @app.post("/api/v1/calls/{interaction_id}/segments")
    async def push_segment(interaction_id: str, payload: SegmentPayload):
        seg = await pipeline.ingest_segment(interaction_id, payload)
        return {"success": True, "segment": seg, "widgets": hub.count(interaction_id)}

    @app.post("/api/v1/calls/{interaction_id}/end")
    async def end_call(interaction_id: str):
        return await pipeline.end_call(interaction_id)

    # ----------------------------------------------------------- tickets
    @app.get("/api/v1/tickets")
    def list_tickets(status: Optional[str] = None, district: Optional[str] = None, limit: int = 100):
        if status and status not in TICKET_STATUSES:
            raise HTTPException(422, f"status must be one of {list(TICKET_STATUSES)}")
        tickets = store.list_tickets(status=status, district=district, limit=limit)
        return {"total": len(tickets), "tickets": tickets}

    @app.get("/api/v1/tickets/{ticket_id}")
    def get_ticket(ticket_id: str):
        ticket = store.get(ticket_id)
        if ticket is None:
            raise HTTPException(404, "ไม่พบ Ticket")
        return ticket

    @app.patch("/api/v1/tickets/{ticket_id}/status")
    async def set_ticket_status(ticket_id: str, body: StatusUpdate):
        ticket = await pipeline.update_status(ticket_id, body.status)
        if ticket is None:
            raise HTTPException(404, "ไม่พบ Ticket")
        return ticket

    @app.post("/api/v1/tickets/{ticket_id}/dispatch")
    async def dispatch(ticket_id: str, body: Optional[DispatchRequest] = None):
        ticket = store.get(ticket_id)
        if ticket is None:
            raise HTTPException(404, "ไม่พบ Ticket")
        iid = (body.interaction_id if body and body.interaction_id else None) or ticket["interaction_id"]
        return await pipeline.dispatch_ticket(iid, ticket_id)

    # --------------------------------------------- conversational voicebot
    @app.post("/api/v1/voicebot/converse")
    async def voicebot_converse(req: VoicebotChatRequest):
        """Tier-1 voicebot: understand -> answer from Civic RAG, or take the complaint."""
        lang = req.language or "th"
        if lang == "en":
            reply = await _english_reply(req)
            return {"success": True, "reply_text": reply, "tts_audio_url": tts_url(reply, "en"), "intent": None}

        if req.interaction_id:
            result = await pipeline.process_call(
                GenesysWebhookPayload(interaction_id=req.interaction_id, transcript=req.message),
                reviewed_location=req.reviewed_location,
            )
            if req.reviewed_location is not None and result["duplicate"]:
                existing = store.get(result["ticket_id"])
                if existing and (
                    existing["district"] != req.reviewed_location.district
                    or existing["location_detail"] != req.reviewed_location.location_detail
                ):
                    raise HTTPException(409, "คำร้องนี้บันทึกไว้แล้วโดยใช้ข้อมูลพื้นที่เดิม")
            reply, intent = result["reply_text"], result["analysis"]["intent"]
            extra = {"next_action": result["next_action"], "ticket_id": result["ticket_id"]}
        else:
            c = await classifier.classify(req.message)
            intent, extra = c.intent, {}
            if c.intent == "inquiry":
                reply = (await rag.answer(req.message, topic=c.inquiry_topic)).text
            elif c.intent == "complaint":
                reply = f"รับทราบเรื่อง{c.sub_category or c.category}แล้วค่ะ จะส่งเรื่องให้{c.target_unit}ดำเนินการ"
            else:
                reply = "ขออภัยค่ะ รบกวนพูดอีกครั้งได้ไหมคะ"
        return {"success": True, "reply_text": reply, "tts_audio_url": tts_url(reply), "intent": intent, **extra}

    async def _english_reply(req: VoicebotChatRequest) -> str:
        fallback = "The Bangkok 1555 hotline has received your request and will coordinate for you."
        if llm is None:
            return fallback
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI Contact Center Agent for Bangkok 1555 Civic Hotline. Politely assist "
                    "foreign residents and tourists with concise, accurate information. If they report an "
                    "issue, confirm details and state it will be dispatched to the district office."
                ),
            },
            *(req.conversation_history or []),
            {"role": "user", "content": req.message},
        ]
        try:
            return (await llm.chat(messages, max_tokens=150, temperature=0.3, timeout=10.0)).strip() or fallback
        except LLMError as exc:
            logger.warning("English voicebot fallback: %s", exc)
            return fallback

    @app.get("/api/v1/tts/synthesize")
    async def synthesize_speech(text: str = Query(..., max_length=600), lang: str = "th"):
        """Thai / English neural voice via edge-tts, returned as audio/mpeg."""
        voice = (os.getenv("THAI_TTS_VOICE") or "th-TH-PremwadeeNeural") if lang == "th" else "en-US-AndrewMultilingualNeural"
        try:
            import edge_tts

            audio = b""
            async for chunk in edge_tts.Communicate(text, voice).stream():
                if chunk["type"] == "audio":
                    audio += chunk["data"]
            return Response(content=audio, media_type="audio/mpeg")
        except Exception as exc:
            logger.error("TTS synthesis error: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/v1/outbound/call-citizen")
    async def trigger_outbound_call(req: OutboundCallRequest):
        """Proactive AI call telling the citizen their ticket was resolved (Genesys Outbound API hook)."""
        script_th = (
            "สวัสดีค่ะ โทรจากศูนย์รับเรื่องสายด่วน กทม. 1555 นะคะ "
            f"ขอแจ้งความคืบหน้ารหัสคำร้อง {spoken_ticket_id(req.ticket_id)} ขณะนี้ฝ่ายที่เกี่ยวข้อง "
            f"สำนักงานเขต{req.district} ได้ดำเนินการ {req.resolution_summary} เรียบร้อยแล้วค่ะ "
            "ขอบคุณที่ช่วยแจ้งข้อมูลเพื่อกรุงเทพฯ ของเรานะคะ"
        )
        logger.info("Queueing AI outbound call for ticket %s", req.ticket_id)  # never log the phone number
        return {
            "success": True,
            "status": "outbound_call_queued",
            "target_ani": req.phone_number,
            "spoken_script": script_th,
            "tts_preview_url": tts_url(script_th, req.language or "th"),
        }

    # ----------------------------------------------------- WebSocket hub
    async def _widget_socket(websocket: WebSocket, channel: str) -> None:
        await hub.connect(channel, websocket)
        await hub.send(
            websocket,
            make_event("connected", channel, {"protocol": 1, "server_time": dt.datetime.now().isoformat()}),
        )
        if channel != MONITOR_CHANNEL:
            await hub.send(websocket, make_event("snapshot", channel, pipeline.snapshot(channel)))
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                    if not isinstance(message, dict):
                        raise ValueError("not an object")
                except ValueError:
                    await hub.send(websocket, make_event("error", channel, {"message": "ต้องส่งเป็น JSON object"}))
                    continue
                logger.info("Widget action %s on %s", message.get("action"), channel)
                reply = await pipeline.handle_widget_message(channel, message)
                if reply is not None:
                    await hub.send(websocket, make_event(reply[0], channel, reply[1]))
        except WebSocketDisconnect:
            pass
        finally:
            hub.disconnect(channel, websocket)
            logger.info("Widget disconnected from %s", channel)

    @app.websocket("/ws/agent/{interaction_id}")
    async def agent_widget_ws(websocket: WebSocket, interaction_id: str):
        await _widget_socket(websocket, interaction_id)

    @app.websocket("/ws/monitor")
    async def monitor_ws(websocket: WebSocket):
        """Supervisor / demo board: receives the events of every call."""
        await _widget_socket(websocket, MONITOR_CHANNEL)

    if _WIDGET_DIR.is_dir():  # handy for local demos; nginx serves it in production
        app.mount("/widget", StaticFiles(directory=_WIDGET_DIR, html=True), name="widget")

    return app
