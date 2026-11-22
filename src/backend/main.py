"""
BKK CivicVoice AI - Core FastAPI Backend Middleware
Handles Genesys Cloud CX Webhooks, Typhoon/Gemma AI Reasoning, and Agent Widget WebSockets.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime
import json
import logging

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
