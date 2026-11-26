"""Deterministic keyword engine.

It has two jobs: (1) a safety net when the LLM is slow/unreachable/returns garbage, and
(2) a cross-check on the LLM output (explicit district mention, safety keywords).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .districts import extract_district
from .schemas import CATEGORY_PROFILE, SUB_CATEGORY_PROFILE

# (type key, category, sub category, {keyword: weight}) - order is the tie-break priority.
_COMPLAINT_TYPES: list[tuple[str, str, str | None, dict[str, int]]] = [
    ("emergency", "อื่นๆ", "เหตุฉุกเฉิน", {
        "ไฟไหม้": 5, "เพลิงไหม้": 5, "ตึกถล่ม": 5,
        "ดินสไลด์": 4, "จมน้ำ": 5,
    }),
    ("flood", "อื่นๆ", "ท่อระบายน้ำ/น้ำท่วม", {
        "น้ำท่วม": 4, "ท่วมขัง": 4, "ท่อระบายน้ำ": 4, "ท่อตัน": 4, "ท่อแตก": 4, "ฝาท่อ": 3,
        "น้ำเอ่อ": 3, "น้ำขัง": 3, "ระบายน้ำ": 3, "ท่อน้ำ": 2, "ท่วม": 2,
    }),
    ("traffic", "ผิดกฎจราจร", None, {
        "จอดรถ": 3, "จอดขวาง": 4, "จอดซ้อนคัน": 4, "จอดกีดขวาง": 4, "ย้อนศร": 4, "ฝ่าไฟแดง": 4,
        "ผิดกฎจราจร": 4, "ขึ้นทางเท้า": 5, "มอเตอร์ไซค์ขึ้น": 3, "มอไซค์ขึ้น": 3, "ขวางทาง": 2,
    }),
    ("sidewalk", "ทางเท้า", None, {
        "ทางเท้า": 4, "ฟุตบาท": 4, "บาทวิถี": 4, "ทางเดินเท้า": 4, "กระเบื้อง": 2, "สะดุด": 2,
    }),
    ("light", "ไฟฟ้า", None, {
        "ไฟส่องสว่าง": 4, "ไฟดับ": 4, "ไฟถนน": 4, "หลอดไฟ": 4, "เสาไฟ": 4, "ไฟไม่ติด": 4,
        "ไฟทางเท้า": 5, "ไฟทาง": 3, "สายไฟ": 3, "ไฟรั่ว": 4, "ไฟช็อต": 4, "ไฟดูด": 4, "ไฟฟ้า": 3, "หม้อแปลง": 3, "ไฟเสีย": 3, "มืด": 2,
    }),
    ("clean", "ความสะอาด", None, {
        "ขยะ": 4, "ถังขยะ": 4, "กองขยะ": 4, "รถขยะ": 3, "สิ่งปฏิกูล": 4, "เหม็น": 3, "สกปรก": 3,
    }),
    ("road", "ถนน", None, {
        "ถนนพัง": 4, "ถนนเป็นหลุม": 4, "หลุม": 3, "ลาดยาง": 3, "ผิวจราจร": 3, "ผิวถนน": 3,
        "ถนน": 2, "ยุบ": 2,
    }),
    ("tree", "อื่นๆ", "ต้นไม้", {
        "ต้นไม้": 4, "กิ่งไม้": 4, "ต้นไม้ล้ม": 5,
    }),
    ("noise", "อื่นๆ", "เสียงรบกวน", {
        "เสียงดัง": 4, "เสียงรบกวน": 4, "เสียงเพลง": 3, "คาราโอเกะ": 3,
    }),
    ("vendor", "อื่นๆ", "หาบเร่แผงลอย", {
        "หาบเร่": 4, "แผงลอย": 4, "ตั้งแผง": 3, "ค้าขายกีดขวาง": 4, "รถเข็น": 2,
    }),
    ("dust", "อื่นๆ", "ฝุ่นควัน/กลิ่น", {
        "ฝุ่น": 3, "pm2.5": 4, "pm 2.5": 4, "ควัน": 3, "เผาขยะ": 4, "กลิ่น": 2,
    }),
    ("animal", "อื่นๆ", "สัตว์", {
        "สุนัขจรจัด": 4, "หมาจรจัด": 4, "แมวจรจัด": 4, "สุนัข": 2, "งูเห่า": 4, "งูเหลือม": 4, "สัตว์": 2,
    }),
    ("equipment", "อื่นๆ", "อุปกรณ์/อาคารชำรุด", {
        "ป้ายชำรุด": 4, "ราวสะพาน": 4, "สะพานลอย": 3, "สัญญาณไฟจราจร": 4, "อาคาร": 2, "ชำรุด": 2,
    }),
]

_GENERIC_COMPLAINT = {
    "ร้องเรียน": 2, "ร้องทุกข์": 2, "ปัญหา": 1, "แจ้งเหตุ": 2, "แจ้งเรื่อง": 1, "เดือดร้อน": 2,
    "พัง": 1, "แตก": 1, "เสียหาย": 1, "รบกวน": 1, "อันตราย": 1, "ช่วยมาดู": 2, "ส่งคนมา": 2,
}

_INQUIRY_KEYWORDS = {
    "สอบถาม": 2, "ขอถาม": 2, "อยากทราบ": 2, "อยากถาม": 2, "ขั้นตอน": 2, "ต้องเตรียม": 2,
    "ต้องใช้เอกสาร": 2, "เอกสาร": 1, "ค่าธรรมเนียม": 2, "เปิดไหม": 3, "เปิดทำการ": 2, "กี่โมง": 3,
    "วันเสาร์": 1, "ทำบัตร": 3, "บัตรประชาชน": 3, "ทะเบียนบ้าน": 3, "ย้ายเข้า": 3, "ย้ายออก": 3,
    "ย้ายที่อยู่": 3, "แจ้งเกิด": 3, "แจ้งตาย": 3, "เพิ่มชื่อ": 3, "เบี้ยยังชีพ": 4,
    "เบี้ยผู้สูงอายุ": 4, "เบี้ยคนชรา": 4, "ได้ไหม": 1, "หรือไม่": 1, "ยังไง": 1, "อย่างไร": 1,
    "ภาษีที่ดิน": 3,
}

_TOPIC_KEYWORDS = {
    "id_card": ("บัตรประชาชน", "ทำบัตร", "บัตรหาย", "บัตรหมดอายุ", "บัตร ปชช", "บัตรปชช"),
    "house_registration": ("ทะเบียนบ้าน", "ย้ายเข้า", "ย้ายออก", "ย้ายที่อยู่", "แจ้งเกิด", "แจ้งตาย", "เพิ่มชื่อ", "ย้ายบ้าน"),
    "elderly_allowance": ("เบี้ยยังชีพ", "เบี้ยผู้สูงอายุ", "เบี้ยคนชรา", "ผู้สูงอายุ", "คนชรา"),
}

TOPIC_TH = {
    "id_card": "การทำบัตรประชาชน",
    "house_registration": "ทะเบียนบ้าน",
    "elderly_allowance": "เบี้ยยังชีพผู้สูงอายุ",
    "other": "ข้อมูลบริการของ กทม.",
}

_HIGH_URGENCY = (
    "อันตราย", "ล้ม", "เจ็บ", "บาดเจ็บ", "ท่วม", "ฉุกเฉิน", "ไฟไหม้", "เพลิงไหม้", "ไฟช็อต",
    "ไฟดูด", "ไฟรั่ว", "ท่อแตก", "ถล่ม", "ด่วนมาก", "เร่งด่วน", "จมน้ำ", "เสียชีวิต", "ตาย", "ฝาท่อเปิด",
    "ฝาท่อหาย",
)
_LOW_URGENCY = ("ไม่เร่งด่วน", "ไม่รีบ", "ไม่ด่วน", "เมื่อสะดวก", "ว่างๆ", "ไม่เป็นไร")
_QUESTION_MARKERS = ("ไหม", "หรือเปล่า", "หรือไม่", "อย่างไร", "ยังไง", "กี่", "หรือยัง")

# A marker (ซอย/ถนน/...) must be followed directly by the name ("ซอยอารีย์") or by a number
# ("ซอย 50"); "ถนน มอเตอร์ไซค์..." (a space then more speech) is not a street.
_LOCATION_RE = re.compile(
    r"(?:ปากซอย|ซอย|ถนน|ถ\.|แยก|ตรอก|หมู่บ้าน|ซ\.)"
    r"(?:\s*[0-9]+(?:/[0-9]+)?|[ก-๙A-Za-z/\-.][ก-๙A-Za-z0-9/\-.]*(?:\s*[0-9]+(?:/[0-9]+)?)?)"
)
_LOCATION_STOP = (
    "มี", "เป็น", "น้ำ", "แล้ว", "ครับ", "ค่ะ", "คะ", "นะ", "ที่", "เขต", "แถว", "ช่วย", "อยาก",
    "ทาง", "ไฟ", "ขยะ", "ถนน", "หลุม", "เกิด", "พัง", "แตก",
)
_MAX_LOCATION_LEN = 40


@dataclass
class RuleResult:
    intent: str
    category: str | None
    sub_category: str | None
    district: str | None
    location_detail: str
    urgency: str
    inquiry_topic: str | None
    complaint_score: int = 0
    inquiry_score: int = 0
    matched: list[str] = field(default_factory=list)


def _score(text: str, table: dict[str, int]) -> tuple[int, list[str]]:
    hits = [kw for kw in table if kw in text]
    return sum(table[kw] for kw in hits), hits


def detect_urgency(text: str) -> str:
    lowered = text.lower()
    if any(kw in lowered for kw in _HIGH_URGENCY):
        return "high"
    if any(kw in lowered for kw in _LOW_URGENCY):
        return "low"
    return "medium"


def extract_location(text: str) -> str:
    """Pull street/soi phrases out of the speech (never returns the raw transcript)."""
    parts: list[str] = []
    for match in _LOCATION_RE.finditer(text):
        phrase = match.group(0).strip()
        # cut at the first stop word that follows the leading marker + one name character
        head = re.match(r"(ปากซอย|ซอย|ถนน|ถ\.|แยก|ตรอก|หมู่บ้าน|ซ\.)\s*", phrase)
        marker_len = head.end() if head else 0
        body = phrase[marker_len:]
        if any(body.startswith(stop) for stop in _LOCATION_STOP):
            continue  # e.g. "ถนนพัง" is a problem, not a street name
        cut = len(body)
        for stop in _LOCATION_STOP:
            idx = body.find(stop, 1)
            if idx != -1:
                cut = min(cut, idx)
        body = body[:cut].strip()
        if not body:
            continue
        marker = head.group(1) if head else ""
        candidate = f"{marker}{body}"[:_MAX_LOCATION_LEN]
        if candidate not in parts:
            parts.append(candidate)
    return " ".join(parts[:2])


def detect_topic(text: str) -> str:
    for topic, words in _TOPIC_KEYWORDS.items():
        if any(w in text for w in words):
            return topic
    return "other"


def analyze(text: str) -> RuleResult:
    """Keyword-based understanding of one utterance."""
    normalized = (text or "").strip()
    lowered = normalized.lower()

    best_type: tuple[int, str, str | None] | None = None
    matched: list[str] = []
    for _key, category, sub, table in _COMPLAINT_TYPES:
        score, hits = _score(lowered, table)
        if score and (best_type is None or score > best_type[0]):
            best_type = (score, category, sub)
            matched = hits

    generic_score, generic_hits = _score(lowered, _GENERIC_COMPLAINT)
    complaint_score = (best_type[0] if best_type else 0) + generic_score
    inquiry_score, inquiry_hits = _score(lowered, _INQUIRY_KEYWORDS)
    if any(m in lowered for m in _QUESTION_MARKERS):
        inquiry_score += 1

    if complaint_score == 0 and inquiry_score <= 1:
        intent = "unclear"
    elif inquiry_score > complaint_score:
        intent = "inquiry"
    else:
        intent = "complaint"

    category = sub = None
    if intent == "complaint":
        if best_type:
            _, category, sub = best_type
        else:
            category = "อื่นๆ"

    return RuleResult(
        intent=intent,
        category=category,
        sub_category=sub,
        district=extract_district(normalized),
        location_detail=extract_location(normalized) if intent == "complaint" else "",
        urgency=detect_urgency(normalized) if intent == "complaint" else "low",
        inquiry_topic=detect_topic(lowered) if intent == "inquiry" else None,
        complaint_score=complaint_score,
        inquiry_score=inquiry_score,
        matched=matched + generic_hits + inquiry_hits,
    )


def profile_for(category: str | None, sub_category: str | None) -> dict:
    """SLA / unit / action for a category (sub category wins when known)."""
    if sub_category and sub_category in SUB_CATEGORY_PROFILE:
        return SUB_CATEGORY_PROFILE[sub_category]
    return CATEGORY_PROFILE.get(category or "อื่นๆ", CATEGORY_PROFILE["อื่นๆ"])
