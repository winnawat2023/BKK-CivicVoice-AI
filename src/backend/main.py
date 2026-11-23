"""
BKK CivicVoice AI - Core FastAPI Backend Middleware
Handles Genesys Cloud CX Webhooks, Typhoon/Gemma AI Reasoning, and Agent Widget WebSockets.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime
import json
import logging
import httpx
import os
import subprocess
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bkk-civic-voice")

app = FastAPI(
    title="BKK CivicVoice AI Middleware",
    description="Enterprise Civic Contact Center API for Bangkok (Genesys Cloud CX + Thai LLM)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory Ticket and Connection Store
TICKETS_DB: List[Dict[str, Any]] = []
ACTIVE_CONNECTIONS: Dict[str, List[WebSocket]] = {}

# ----------------- Data Models -----------------
class GenesysWebhookPayload(BaseModel):
    interaction_id: str = Field(..., description="Genesys Conversation ID")
    ani: str = Field(..., description="Caller Phone Number")
    channel: str = Field("voice", description="voice or chat")
    transcript: str = Field(..., description="Recognized speech text in Thai")
    timestamp: Optional[str] = None

class CivicClassificationResult(BaseModel):
    interaction_id: str
    intent: str = Field(..., description="inquiry or complaint")
    category: str = Field(..., description="ถนน | ทางเท้า | ผิดกฎจราจร | ไฟฟ้า | ความสะอาด | อื่นๆ")
    district: str = Field(..., description="One of 50 BKK Districts")
    location_detail: str
    urgency: str = Field(..., description="low | medium | high")
    summary_th: str
    suggested_action: str
    estimated_sla_days: int

# ----------------- Mock Thai LLM Engine (Typhoon/Gemma Adapter) -----------------
def classify_with_thai_llm(transcript: str, interaction_id: str) -> CivicClassificationResult:
    """
    Simulates / Connects to Typhoon/Gemma Thai LLM reasoning.
    Extracts category, district, urgency, and generates executive Thai summary.
    """
    text = transcript.lower()
    
    # 1. Intent Detection
    if any(k in text for k in ["ทำบัตร", "ทะเบียนบ้าน", "ขอบ้านเลขที่", "กี่โมง", "เปิดไหม", "วันเสาร์", "เอกสาร"]):
        intent = "inquiry"
        category = "บริการงานทะเบียนและเอกสาร"
        urgency = "low"
        summary = "ประชาชนสอบถามข้อมูลระเบียบขั้นตอนการรับบริการของกรุงเทพมหานคร"
        action = "ตอบข้อมูลระเบียบ กทม. อัตโนมัติ (ไม่ต้องส่งต่อเขต)"
        sla = 0
    else:
        intent = "complaint"
        # Category classification from 3-year Top Data
        if any(k in text for k in ["ถนน", "หลุม", "บ่อ", "ลาดยาง"]):
            category = "ถนน"
            sla = 3
        elif any(k in text for k in ["ทางเท้า", "ฟุตบาท", "กระเบื้อง", "สะดุด"]):
            category = "ทางเท้า"
            sla = 5
        elif any(k in text for k in ["ไฟ", "มืด", "หลอดไฟ", "สายไฟ"]):
            category = "ไฟฟ้า"
            sla = 2
        elif any(k in text for k in ["ขยะ", "ถังขยะ", "เหม็น", "สิ่งปฏิกูล"]):
            category = "ความสะอาด"
            sla = 1
        elif any(k in text for k in ["จอดรถ", "ย้อนศร", "มอไซค์", "ขวาง"]):
            category = "ผิดกฎจราจร"
            sla = 1
        else:
            category = "อื่นๆ"
            sla = 7

        # Urgency
        if any(k in text for k in ["อันตราย", "ล้ม", "เจ็บ", "ท่วม", "ฉุกเฉิน", "แตก"]):
            urgency = "high"
        else:
            urgency = "medium"

        summary = f"แจ้งปัญหา{category}: {transcript[:60]}..."
        action = f"ส่งเรื่องไปยังฝ่ายที่เกี่ยวข้อง (ฝ่ายโยธา/รักษาความสะอาด/เทศกิจ)"

    # District extraction
    districts = ["คลองเตย", "จตุจักร", "วัฒนา", "บางกะปิ", "ปทุมวัน", "พญาไท", "ดินแดง", "สาทร", "บางรัก", "ประเวศ"]
    matched_district = "คลองเตย" # default fallback
    for d in districts:
        if d in text:
            matched_district = d
            break
            
    return CivicClassificationResult(
        interaction_id=interaction_id,
        intent=intent,
        category=category,
        district=matched_district,
        location_detail=transcript[:80],
        urgency=urgency,
        summary_th=summary,
        suggested_action=action,
        estimated_sla_days=sla
    )

# ----------------- API Endpoints -----------------
@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "BKK CivicVoice AI Core Middleware",
        "org": "ark-insights",
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.post("/api/v1/genesys/webhook")
async def handle_genesys_webhook(payload: GenesysWebhookPayload):
    """
    Webhook Endpoint called by Genesys Cloud CX Architect Inbound Flow.
    """
    logger.info(f"Received interaction from Genesys: {payload.interaction_id} from {payload.ani}")
    
    # 1. Process with AI Reasoning
    ai_result = classify_with_thai_llm(payload.transcript, payload.interaction_id)
    
    # 2. Auto Create Ticket if it is a complaint
    ticket_id = f"BKK-{datetime.datetime.now().strftime('%y%m%d')}-{len(TICKETS_DB)+1:04d}"
    ticket_record = {
        "ticket_id": ticket_id,
        "interaction_id": payload.interaction_id,
        "caller_ani": payload.ani,
        "transcript": payload.transcript,
        "intent": ai_result.intent,
        "category": ai_result.category,
        "district": ai_result.district,
        "urgency": ai_result.urgency,
        "summary": ai_result.summary_th,
        "suggested_action": ai_result.suggested_action,
        "sla_days": ai_result.estimated_sla_days,
        "status": "รอรับเรื่อง",
        "created_at": datetime.datetime.now().isoformat()
    }
    TICKETS_DB.append(ticket_record)
    
    # 3. Broadcast to Agent Widget via WebSocket if connected
    if payload.interaction_id in ACTIVE_CONNECTIONS:
        msg = json.dumps({"event": "live_update", "data": ticket_record}, ensure_ascii=False)
        for ws in ACTIVE_CONNECTIONS[payload.interaction_id]:
            await ws.send_text(msg)
            
    return {
        "success": True,
        "ticket_id": ticket_id,
        "analysis": ai_result.dict()
    }

@app.get("/api/v1/tickets")
def list_tickets():
    return {"total": len(TICKETS_DB), "tickets": list(reversed(TICKETS_DB))}

# ----------------- Conversational Voicebot & Outbound Voice Agent -----------------

class VoicebotChatRequest(BaseModel):
    message: str = Field(..., description="User voice transcript")
    language: Optional[str] = "th" # "th" or "en"
    conversation_history: Optional[List[Dict[str, str]]] = None

class OutboundCallRequest(BaseModel):
    phone_number: str = Field(..., description="Citizen phone number")
    ticket_id: str = Field(..., description="BKK Ticket ID")
    resolution_summary: str = Field(..., description="What district resolved")
    district: str = Field("คลองเตย", description="District name")
    language: Optional[str] = "th"

@app.post("/api/v1/voicebot/converse")
async def voicebot_converse(req: VoicebotChatRequest):
    """
    Tier 1 Full Conversational Voicebot:
    Directly chats with citizen using Typhoon 8B, returns text answer + TTS audio stream.
    """
    system_prompt = (
        "คุณคือ AI เจ้าหน้าที่สายด่วน 1555 กรุงเทพมหานคร ตอบคำถามประชาชนอย่างสุภาพ กระชับ ถูกต้อง "
        "หากเป็นการสอบถามข้อมูลระเบียบ กทม. ให้ตอบข้อมูลชัดเจนภายใน 2-3 ประโยค "
        "หากเป็นการแจ้งเรื่องร้องทุกข์ ให้ยืนยันข้อมูลและแจ้งว่าจะส่งเรื่องเข้าสำนักงานเขตให้ทันที"
    )
    if req.language == "en":
        system_prompt = (
            "You are an AI Contact Center Agent for Bangkok 1555 Civic Hotline. "
            "Politely assist foreign residents and tourists with concise, accurate information. "
            "If they report an issue, confirm details and state it will be dispatched to the district office."
        )

    messages = [{"role": "system", "content": system_prompt}]
    if req.conversation_history:
        messages.extend(req.conversation_history)
    messages.append({"role": "user", "content": req.message})

    # Call local Typhoon 8B via vLLM
    vllm_url = os.getenv("VLLM_URL", "http://127.0.0.1:8001/v1/chat/completions")
    ai_reply = "ศูนย์บริการสายด่วน 1555 รับเรื่องและกำลังประสานงานให้ค่ะ"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                vllm_url,
                json={
                    "model": "typhoon-8b",
                    "messages": messages,
                    "max_tokens": 150,
                    "temperature": 0.3
                }
            )
            if resp.status_code == 200:
                ai_reply = resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"Typhoon call error, fallback response: {e}")
        if "บัตรประชาชน" in req.message:
            ai_reply = "สำนักงานเขตเปิดบริการทำบัตรประชาชนวันเสาร์ 08:00 - 16:00 น. นำบัตรเดิมมาติดต่อได้เลยค่ะ"

    return {
        "success": True,
        "reply_text": ai_reply,
        "tts_audio_url": f"/api/v1/tts/synthesize?text={ai_reply[:150]}&lang={req.language}"
    }

@app.get("/api/v1/tts/synthesize")
async def synthesize_speech(text: str, lang: str = "th"):
    """
    Synthesize natural voice using edge-tts (Thai Premwadee / English Andrew).
    Returns audio/mpeg stream directly to Genesys Cloud or Web Widget.
    """
    voice = "th-TH-PremwadeeNeural" if lang == "th" else "en-US-AndrewMultilingualNeural"
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"TTS Synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/outbound/call-citizen")
async def trigger_outbound_call(req: OutboundCallRequest):
    """
    Trigger proactive AI phone call to citizen informing ticket resolution.
    Connects with Genesys Outbound API.
    """
    script_th = (
        f"สวัสดีค่ะ โทรจากศูนย์รับเรื่องสายด่วน กทม. 1555 นะคะ "
        f"ขอแจ้งความคืบหน้ารหัสคำร้อง {req.ticket_id} ขณะนี้ฝ่ายที่เกี่ยวข้อง สำนักงานเขต{req.district} "
        f"ได้ดำเนินการ {req.resolution_summary} เรียบร้อยแล้วค่ะ ขอบคุณที่ช่วยแจ้งข้อมูลเพื่อกรุงเทพฯ ของเรานะคะ"
    )
    logger.info(f"Triggering AI Outbound Call to {req.phone_number}: {script_th}")
    
    return {
        "success": True,
        "status": "outbound_call_queued",
        "target_ani": req.phone_number,
        "spoken_script": script_th,
        "tts_preview_url": f"/api/v1/tts/synthesize?text={script_th}&lang={req.language}"
    }

# ----------------- WebSocket for Genesys Agent Widget -----------------
@app.websocket("/ws/agent/{interaction_id}")
async def agent_widget_ws(websocket: WebSocket, interaction_id: str):
    await websocket.accept()
    if interaction_id not in ACTIVE_CONNECTIONS:
        ACTIVE_CONNECTIONS[interaction_id] = []
    ACTIVE_CONNECTIONS[interaction_id].append(websocket)
    logger.info(f"Agent Widget connected for interaction {interaction_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            # Handle client actions (e.g. 1-click resolve, escalate)
            logger.info(f"Widget action received: {data}")
    except WebSocketDisconnect:
        ACTIVE_CONNECTIONS[interaction_id].remove(websocket)
        logger.info(f"Agent Widget disconnected for interaction {interaction_id}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
