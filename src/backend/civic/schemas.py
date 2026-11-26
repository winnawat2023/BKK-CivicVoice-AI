"""Shared data models and domain constants (categories, urgency levels, SLA table)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

Intent = Literal["complaint", "inquiry", "unclear"]
Urgency = Literal["low", "medium", "high"]

# 5 main problem categories from the 1555 open data (+ "อื่นๆ" for everything else).
CATEGORIES: tuple[str, ...] = ("ถนน", "ทางเท้า", "ผิดกฎจราจร", "ไฟฟ้า", "ความสะอาด", "อื่นๆ")
URGENCY_LEVELS: tuple[str, ...] = ("low", "medium", "high")
URGENCY_TH = {"low": "ต่ำ", "medium": "ปานกลาง", "high": "สูง"}

# Short codes the LLM answers with (cheap to generate); mapped back to the Thai names above.
CATEGORY_CODES: dict[str, str] = {
    "road": "ถนน", "sidewalk": "ทางเท้า", "traffic": "ผิดกฎจราจร",
    "electric": "ไฟฟ้า", "clean": "ความสะอาด", "other": "อื่นๆ",
}
SUB_CATEGORY_CODES: dict[str, str] = {
    "drain": "ท่อระบายน้ำ/น้ำท่วม", "tree": "ต้นไม้", "noise": "เสียงรบกวน", "vendor": "หาบเร่แผงลอย",
    "dust": "ฝุ่นควัน/กลิ่น", "animal": "สัตว์", "equipment": "อุปกรณ์/อาคารชำรุด", "emergency": "เหตุฉุกเฉิน",
}

# Ticket workflow (FR4.3).
TICKET_STATUSES: tuple[str, ...] = ("รับเรื่องแล้ว", "กำลังดำเนินการ", "แก้ไขเสร็จ")

# Estimated SLA in days, responsible unit and default next action per category.
# SLA values are working estimates (assumption) carried over from the first prototype.
CATEGORY_PROFILE: dict[str, dict[str, Any]] = {
    "ถนน": {"sla_days": 3, "unit": "ฝ่ายโยธา สำนักงานเขต", "action": "ส่งฝ่ายโยธาตรวจสอบและซ่อมแซมผิวถนน"},
    "ทางเท้า": {"sla_days": 5, "unit": "ฝ่ายโยธา สำนักงานเขต", "action": "ส่งฝ่ายโยธาตรวจสอบและซ่อมแซมทางเท้า"},
    "ผิดกฎจราจร": {"sla_days": 1, "unit": "ฝ่ายเทศกิจ สำนักงานเขต", "action": "ส่งฝ่ายเทศกิจ/ตำรวจจราจรตรวจสอบ"},
    "ไฟฟ้า": {"sla_days": 2, "unit": "ฝ่ายโยธา (ไฟฟ้าสาธารณะ) สำนักงานเขต", "action": "ส่งฝ่ายโยธาซ่อมไฟส่องสว่างสาธารณะ"},
    "ความสะอาด": {"sla_days": 1, "unit": "ฝ่ายรักษาความสะอาดและสวนสาธารณะ", "action": "ส่งฝ่ายรักษาความสะอาดเก็บขยะ/ทำความสะอาด"},
    "อื่นๆ": {"sla_days": 7, "unit": "ฝ่ายปกครอง สำนักงานเขต", "action": "ส่งเจ้าหน้าที่ตรวจสอบและจัดหมวดต่อ"},
}

# Finer-grained types inside "อื่นๆ" (and flooding, which the PRD demo uses).
SUB_CATEGORY_PROFILE: dict[str, dict[str, Any]] = {
    "ท่อระบายน้ำ/น้ำท่วม": {"sla_days": 2, "unit": "ฝ่ายโยธา (ระบายน้ำ) สำนักงานเขต", "action": "ส่งฝ่ายโยธา/สำนักการระบายน้ำตรวจสอบท่อและน้ำท่วมขัง"},
    "ต้นไม้": {"sla_days": 3, "unit": "ฝ่ายรักษาความสะอาดและสวนสาธารณะ", "action": "ส่งฝ่ายสวนสาธารณะตัดแต่ง/เคลียร์ต้นไม้"},
    "เสียงรบกวน": {"sla_days": 3, "unit": "ฝ่ายสิ่งแวดล้อมและสุขาภิบาล", "action": "ส่งฝ่ายสิ่งแวดล้อมตรวจสอบเสียงรบกวน"},
    "หาบเร่แผงลอย": {"sla_days": 3, "unit": "ฝ่ายเทศกิจ สำนักงานเขต", "action": "ส่งฝ่ายเทศกิจตรวจสอบหาบเร่แผงลอย"},
    "ฝุ่นควัน/กลิ่น": {"sla_days": 3, "unit": "ฝ่ายสิ่งแวดล้อมและสุขาภิบาล", "action": "ส่งฝ่ายสิ่งแวดล้อมตรวจสอบฝุ่นควัน/กลิ่น"},
    "สัตว์": {"sla_days": 3, "unit": "ฝ่ายสิ่งแวดล้อมและสุขาภิบาล", "action": "ส่งฝ่ายสิ่งแวดล้อมจัดการสัตว์จรจัด/สัตว์อันตราย"},
    "อุปกรณ์/อาคารชำรุด": {"sla_days": 5, "unit": "ฝ่ายโยธา สำนักงานเขต", "action": "ส่งฝ่ายโยธาตรวจสอบสิ่งก่อสร้างชำรุด"},
    "เหตุฉุกเฉิน": {"sla_days": 1, "unit": "ฝ่ายปกครอง/ป้องกันฯ สำนักงานเขต", "action": "ประสานหน่วยฉุกเฉินเขตทันที"},
}


class Classification(BaseModel):
    """Structured result of understanding one caller utterance (the LLM/rules output contract)."""

    intent: Intent
    category: Optional[str] = Field(None, description="One of CATEGORIES; null for inquiries")
    sub_category: Optional[str] = Field(None, description="Finer type, e.g. ท่อระบายน้ำ/น้ำท่วม")
    district: Optional[str] = Field(None, description="One of the 50 BKK districts, no 'เขต' prefix")
    location_detail: str = Field("", description="Extracted street/soi/landmark; never the raw transcript")
    urgency: Urgency = "medium"
    summary_lines: list[str] = Field(default_factory=list, description="Exactly 3 short Thai lines")
    inquiry_topic: Optional[str] = Field(None, description="id_card | house_registration | elderly_allowance | other")
    suggested_action: str = ""
    target_unit: str = ""
    estimated_sla_days: int = 0
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    engine: Literal["llm", "rules"] = "rules"
    understood: bool = True
    needs_location: bool = False

    @property
    def summary_th(self) -> str:
        return " ".join(self.summary_lines)


class GenesysWebhookPayload(BaseModel):
    """Webhook body. design.md §3.1 names the speech field ``text_or_audio_stream``; the first
    prototype (and simulate_call.py) used ``transcript``. Both are accepted."""

    @model_validator(mode="before")
    @classmethod
    def _accept_design_field_name(cls, data: Any) -> Any:
        if isinstance(data, dict) and "transcript" not in data and "text_or_audio_stream" in data:
            data = {**data, "transcript": data["text_or_audio_stream"]}
        return data

    interaction_id: str = Field(..., min_length=1, description="Genesys Conversation ID")
    ani: str = Field("", description="Caller phone number (not stored in the ticket)")
    dnis: Optional[str] = Field(None, description="Dialed number")
    channel: str = "voice"
    transcript: str = Field(..., min_length=1, description="Recognized Thai speech text")
    timestamp: Optional[str] = None


class SegmentPayload(BaseModel):
    """One piece of live transcript (ASR partial/final) pushed into the gateway."""

    text: str = Field(..., min_length=1)
    speaker: Literal["caller", "bot", "agent"] = "caller"
    is_final: bool = True
    ani: Optional[str] = None


class StatusUpdate(BaseModel):
    status: Literal["รับเรื่องแล้ว", "กำลังดำเนินการ", "แก้ไขเสร็จ"]


class VoicebotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User voice transcript")
    language: Optional[str] = "th"
    conversation_history: Optional[list[dict[str, str]]] = None
    interaction_id: Optional[str] = Field(None, description="When set, a complaint also creates a ticket")


class OutboundCallRequest(BaseModel):
    phone_number: str
    ticket_id: str
    resolution_summary: str
    district: str = "คลองเตย"
    language: Optional[str] = "th"
