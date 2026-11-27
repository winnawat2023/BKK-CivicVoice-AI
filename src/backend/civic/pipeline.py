"""Call pipeline: transcript -> understanding -> (RAG answer | ticket) -> live events for the widget."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .classifier import CivicClassifier, build_summary_lines
from .config import Settings
from .hub import CallSession, ConnectionHub, SessionManager, make_event
from .rag import RagService
from .rules import TOPIC_TH
from .schemas import (
    TICKET_STATUSES,
    URGENCY_TH,
    Classification,
    GenesysWebhookPayload,
    ReviewedLocation,
    SegmentPayload,
)
from .store import TicketStore

logger = logging.getLogger("bkk-civic-voice.pipeline")

MAX_UNCLEAR_RETRIES = 2  # FR7.1: re-ask at most twice, then transfer

ASK_LOCATION_TH = "ขอทราบชื่อซอยหรือถนน และเขตที่เกิดเหตุด้วยค่ะ"
ASK_REPEAT_TH = "ขออภัยค่ะ ไม่แน่ใจว่าต้องการแจ้งเรื่องหรือสอบถามข้อมูลอะไร รบกวนพูดอีกครั้งได้ไหมคะ"
TRANSFER_TH = "ขออภัยค่ะ ระบบยังไม่เข้าใจ ขอโอนสายให้เจ้าหน้าที่ดูแลต่อนะคะ"


def spoken_ticket_id(ticket_id: str) -> str:
    """BKK-2026-0007 -> 'BKK 2026 0007' (reads better with Thai TTS)."""
    return ticket_id.replace("-", " ")


def _legacy_category(c: Classification) -> str:
    if c.intent == "inquiry":
        return "สอบถามข้อมูล"
    return c.sub_category or c.category or "อื่นๆ"


def summary_event_data(
    c: Classification, *, ticket: dict[str, Any] | None, answer_text: str | None, provisional: bool = False
) -> dict[str, Any]:
    return {
        "provisional": provisional,
        "intent": c.intent,
        "category": c.category,
        "sub_category": c.sub_category,
        "district": c.district,
        "location_detail": c.location_detail,
        "urgency": c.urgency,
        "urgency_th": URGENCY_TH[c.urgency],
        "summary_lines": c.summary_lines,
        "target_unit": c.target_unit,
        "suggested_action": c.suggested_action,
        "sla_days": c.estimated_sla_days,
        "inquiry_topic": c.inquiry_topic,
        "ticket_id": ticket["ticket_id"] if ticket else None,
        "answer": answer_text,
        "engine": c.engine,
        "confidence": c.confidence,
        "understood": c.understood,
        "needs_location": c.needs_location,
    }


class CallPipeline:
    def __init__(
        self,
        settings: Settings,
        classifier: CivicClassifier,
        rag: RagService,
        store: TicketStore,
        sessions: SessionManager,
        hub: ConnectionHub,
    ) -> None:
        self.settings = settings
        self.classifier = classifier
        self.rag = rag
        self.store = store
        self.sessions = sessions
        self.hub = hub
        self._live: dict[str, dict[str, bool]] = {}
        self._tasks: set[asyncio.Task] = set()
        self._asked_location: set[str] = set()
        self._unclear_count: dict[str, int] = {}

    # ------------------------------------------------------------ helpers
    def spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def drain(self) -> None:
        """Wait for background analyses (used by tests and graceful shutdown)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _emit(self, interaction_id: str, event: str, data: dict[str, Any]) -> None:
        await self.hub.broadcast(interaction_id, make_event(event, interaction_id, data))

    async def _emit_analysis(
        self,
        session: CallSession,
        c: Classification,
        ticket: dict[str, Any] | None,
        answer_text: str | None,
        provisional: bool = False,
    ) -> dict[str, Any]:
        data = summary_event_data(c, ticket=ticket, answer_text=answer_text, provisional=provisional)
        session.summary = data
        session.classification = c
        iid = session.interaction_id
        await self._emit(iid, "summary", data)
        if ticket is not None:
            session.ticket = ticket
            await self._emit(iid, "ticket", ticket)
        # Legacy event kept for the first widget version (reads data.transcript / data.summary ...).
        await self._emit(
            iid,
            "live_update",
            {
                "transcript": session.caller_text(),
                "caller_ani": session.ani,
                "category": _legacy_category(c),
                "summary": c.summary_th,
                "summary_lines": c.summary_lines,
                "district": c.district or "ไม่ระบุ",
                "urgency": c.urgency,
                "sla_days": c.estimated_sla_days,
                "ticket_id": ticket["ticket_id"] if ticket else None,
                "intent": c.intent,
            },
        )
        return data

    async def _emit_provisional(
        self, session: CallSession, text: str, ticket: dict[str, Any] | None
    ) -> None:
        """Slow LLM ahead? Show an instant rules-based summary first; the LLM result replaces it.

        Skipped when no LLM is configured: the (equally fast) final result is then the only one.
        """
        if not self.classifier.uses_llm or not text:
            return
        fast = self.classifier.classify_fast(text)
        if fast.intent in ("complaint", "inquiry"):
            await self._emit_analysis(session, fast, ticket, None, provisional=True)

    # ------------------------------------------------ live transcript path
    async def ingest_segment(self, interaction_id: str, payload: SegmentPayload) -> dict[str, Any]:
        """ASR pushes transcript pieces here; they reach the widget immediately (no LLM in the way)."""
        session = self.sessions.get_or_create(interaction_id, payload.ani)
        seg = session.add_segment(payload.text, payload.speaker, payload.is_final)
        await self._emit(interaction_id, "transcript", {**seg, "caller_ani": session.ani})
        if payload.is_final and payload.speaker == "caller":
            self.spawn(self.request_live_analysis(interaction_id))
        return seg

    async def request_live_analysis(self, interaction_id: str) -> None:
        """Re-analyse the caller's speech so the widget summary follows the conversation (no ticket)."""
        state = self._live.setdefault(interaction_id, {"running": False, "dirty": False})
        if state["running"]:
            state["dirty"] = True
            return
        state["running"] = True
        try:
            while True:
                state["dirty"] = False
                session = self.sessions.get(interaction_id)
                text = session.caller_text() if session else ""
                if not text:
                    break
                try:
                    ticket = self.store.get_by_interaction(interaction_id)
                    await self._emit_provisional(session, text, ticket)
                    c = await self.classifier.classify(text)
                    answer = None
                    if c.intent == "inquiry":
                        answer = (await self.rag.answer(text, topic=c.inquiry_topic)).text
                    ticket = self.store.get_by_interaction(interaction_id)
                    await self._emit_analysis(session, c, ticket, answer)
                except Exception:
                    logger.exception("Live analysis failed for %s", interaction_id)
                if not state["dirty"]:
                    break
        finally:
            state["running"] = False

    # --------------------------------------------------- full turn (webhook)
    async def process_call(
        self, payload: GenesysWebhookPayload, *, reviewed_location: ReviewedLocation | None = None
    ) -> dict[str, Any]:
        iid = payload.interaction_id
        session = self.sessions.get_or_create(iid, payload.ani)
        text = (payload.transcript or "").strip()
        if not text:
            # Call start (ID + ANI only): nothing to analyse yet, wait for the first utterance.
            return self._await_speech_result(iid)
        last = session.segments[-1] if session.segments else None
        if not (last and last["speaker"] == "caller" and last["is_final"] and last["text"] == text):
            seg = session.add_segment(text, "caller", True)
            await self._emit(iid, "transcript", {**seg, "caller_ani": session.ani})

        full_text = session.caller_text() or text
        await self._emit_provisional(session, full_text, self.store.get_by_interaction(iid))
        c = await self.classifier.classify(full_text)

        ticket: dict[str, Any] | None = None
        created = False
        answer = None
        next_action = "reply"
        reply = ""

        if c.intent == "inquiry":
            answer = await self.rag.answer(full_text, topic=c.inquiry_topic)
            reply = answer.text
            next_action = "transfer_to_agent" if answer.transfer_to_agent else "answer"
            c.summary_lines = [
                c.summary_lines[0] if c.summary_lines else f"ประชาชนสอบถาม: {TOPIC_TH.get(c.inquiry_topic or 'other')}",
                c.summary_lines[1] if len(c.summary_lines) > 1 else "ตอบจากข้อมูลระเบียบ กทม.",
                "ตอบประชาชนจบในสายแล้ว" if answer.answered else "ไม่มีข้อมูลในระบบ ควรโอนสายหาเจ้าหน้าที่",
            ]
        elif c.intent == "unclear":
            count = self._unclear_count.get(iid, 0) + 1
            self._unclear_count[iid] = count
            if count > MAX_UNCLEAR_RETRIES:
                reply, next_action = TRANSFER_TH, "transfer_to_agent"
            else:
                reply, next_action = ASK_REPEAT_TH, "ask_repeat"
        else:  # complaint
            if reviewed_location is not None:
                c.district = reviewed_location.district
                c.location_detail = reviewed_location.location_detail
                c.needs_location = False
                c.summary_lines = build_summary_lines(c)
            if c.needs_location and iid not in self._asked_location:
                self._asked_location.add(iid)  # ask once (FR2.2), then take what we have
                reply, next_action = ASK_LOCATION_TH, "ask_location"
            else:
                ticket, created = self.store.create_ticket(iid, c)
                where = " ".join(p for p in (c.location_detail, f"เขต{c.district}" if c.district else "") if p)
                where = f"บริเวณ{where} " if where else ""
                reply = (
                    f"รับเรื่องแจ้ง{c.sub_category or c.category} {where}เรียบร้อยแล้วค่ะ "
                    f"รหัสคำร้องของคุณคือ {spoken_ticket_id(ticket['ticket_id'])} "
                    f"จะส่งเรื่องให้{c.target_unit}ดำเนินการ"
                )
                next_action = "ticket_created"

        await self._emit_analysis(session, c, ticket, reply if c.intent == "inquiry" else None)

        return {
            "success": True,
            "interaction_id": iid,
            "next_action": next_action,  # reply | answer | ask_location | ask_repeat | ticket_created | transfer_to_agent
            "reply_text": reply,
            "ticket_id": ticket["ticket_id"] if ticket else None,
            "duplicate": bool(ticket) and not created,
            "analysis": {
                **c.model_dump(),
                "summary_th": c.summary_th,
            },
            "answer": (
                {"via": answer.via, "answered": answer.answered, "score": answer.score, "sources": answer.sources}
                if answer
                else None
            ),
        }

    def _await_speech_result(self, iid: str) -> dict[str, Any]:
        """Webhook reply when a call has started but no speech has arrived yet (no reply, no analysis)."""
        ticket = self.store.get_by_interaction(iid)
        return {
            "success": True,
            "interaction_id": iid,
            "next_action": "await_speech",
            "reply_text": "",
            "ticket_id": ticket["ticket_id"] if ticket else None,
            "duplicate": False,
            "analysis": None,
            "answer": None,
        }

    def snapshot(self, interaction_id: str) -> dict[str, Any]:
        """Everything a widget needs to catch up when it connects mid-call."""
        session = self.sessions.get(interaction_id)
        data = session.snapshot() if session else {"caller_ani": "", "transcript": [], "summary": None, "ticket": None}
        if data.get("ticket") is None:
            data["ticket"] = self.store.get_by_interaction(interaction_id)
        return data

    # ------------------------------------------------------------- call end
    async def end_call(self, interaction_id: str) -> dict[str, Any]:
        session = self.sessions.get(interaction_id)
        had_session = session is not None
        await self._emit(interaction_id, "call_ended", {"ticket": session.ticket if session else None})
        # Privacy: transcript and caller number are dropped when the call ends.
        self.sessions.drop(interaction_id)
        self._asked_location.discard(interaction_id)
        self._unclear_count.pop(interaction_id, None)
        self._live.pop(interaction_id, None)
        return {"success": True, "interaction_id": interaction_id, "had_session": had_session}

    # -------------------------------------------------- widget actions / ops
    async def dispatch_ticket(self, interaction_id: str, ticket_id: str | None = None) -> dict[str, Any]:
        ticket = None
        if ticket_id:
            ticket = self.store.mark_dispatched(ticket_id)
        else:
            existing = self.store.get_by_interaction(interaction_id)
            if existing:
                ticket = self.store.mark_dispatched(existing["ticket_id"])
        if ticket is None:
            result = {"success": False, "error": "ไม่พบ Ticket สำหรับสายนี้ (ยังไม่ได้สร้างคำร้อง)"}
            await self._emit(interaction_id, "dispatch_result", result)
            return result
        session = self.sessions.get(interaction_id)
        if session:
            session.ticket = ticket
        result = {
            "success": True,
            "ticket": ticket,
            "message": f"ส่งเรื่อง {ticket['ticket_id']} เข้าสำนักงานเขต{ticket['district'] or ''} เรียบร้อยแล้ว",
        }
        await self._emit(interaction_id, "dispatch_result", result)
        return result

    async def create_ticket_for_call(self, interaction_id: str) -> dict[str, Any]:
        """Widget "Create Ticket" button: file the complaint the AI understood on this call.

        Idempotent (one ticket per call). Refuses when there is nothing categorised yet.
        """
        existing = self.store.get_by_interaction(interaction_id)
        session = self.sessions.get(interaction_id)
        c = session.classification if session else None
        if existing is None and (c is None or c.intent != "complaint" or not c.category):
            result = {"success": False, "error": "ยังไม่พบเรื่องร้องเรียนที่จัดหมวดได้ในสายนี้"}
            await self._emit(interaction_id, "ticket_result", result)
            return result
        created = False
        if existing is None:
            existing, created = self.store.create_ticket(interaction_id, c)
            if session:
                await self._emit_analysis(session, c, existing, None)
        elif session:
            session.ticket = existing
        result = {"success": True, "ticket": existing, "created": created}
        await self._emit(interaction_id, "ticket_result", result)
        return result

    async def update_status(self, ticket_id: str, status: str) -> dict[str, Any] | None:
        if status not in TICKET_STATUSES:
            return None
        ticket = self.store.update_status(ticket_id, status)
        if ticket:
            await self._emit(ticket["interaction_id"], "ticket", ticket)
        return ticket

    async def handle_widget_message(
        self, interaction_id: str, message: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """Handle a JSON action sent by the Agent Widget over the WebSocket.

        Returns an (event, data) reply for the sending widget only, or None when the result was
        already broadcast to every widget watching the call (dispatch / status changes).
        """
        action = message.get("action")
        if action == "ping":
            return "pong", {}
        if action == "snapshot":
            return "snapshot", self.snapshot(interaction_id)
        if action == "create_ticket":
            await self.create_ticket_for_call(interaction_id)
            return None
        if action == "dispatch":
            await self.dispatch_ticket(interaction_id, message.get("ticket_id"))
            return None
        if action == "set_status":
            ticket_id = message.get("ticket_id")
            ticket = await self.update_status(ticket_id, message.get("status", "")) if ticket_id else None
            if ticket is None:
                return "error", {"message": "ticket_id หรือ status ไม่ถูกต้อง"}
            return None
        return "error", {"message": f"ไม่รู้จัก action: {action!r}"}
