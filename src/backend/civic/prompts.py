"""Prompts for the Thai LLM (Typhoon / Gemma). Kept in one place so they can be tuned and tested.

Design note: the DGX vLLM currently decodes at ~13 tokens/s (measured 2026-11-24), so the classification
reply must be tiny (~40 tokens). The model only returns the fields that need judgement, using short
English codes (cheap tokens); the 3-line Thai summary, SLA, unit and action are filled in by code.
"""

from __future__ import annotations

import json

from .districts import DISTRICTS
from .schemas import CATEGORY_CODES, SUB_CATEGORY_CODES

_CATEGORY_HELP = (
    "road=ถนนพัง/หลุม, sidewalk=ทางเท้าชำรุด, traffic=ผิดกฎจราจร(จอดขวาง/ย้อนศร/ขึ้นทางเท้า), "
    "electric=ไฟส่องสว่าง/สายไฟ, clean=ขยะ/กลิ่นเหม็น/ความสะอาด, other=อื่นๆ"
)
_SUB_HELP = (
    "drain=ท่อระบายน้ำ/น้ำท่วม, tree=ต้นไม้, noise=เสียงรบกวน, vendor=หาบเร่แผงลอย, dust=ฝุ่นควัน/กลิ่น, "
    "animal=สัตว์, equipment=อุปกรณ์/อาคารชำรุด, emergency=เหตุฉุกเฉิน(ไฟไหม้/ถล่ม) ใช้เมื่อ category=other เท่านั้น"
)

CLASSIFY_SYSTEM = f"""คุณคือระบบวิเคราะห์เสียงโทรศัพท์ของสายด่วน กทม. 1555
อ่านข้อความที่ถอดจากเสียงประชาชน แล้วตอบเป็น JSON บรรทัดเดียวเท่านั้น ไม่มีข้อความอื่น ไม่ใช้ markdown

รูปแบบ: {{"intent":"complaint|inquiry|unclear","category":"{'|'.join(CATEGORY_CODES)}|null","sub":"{'|'.join(SUB_CATEGORY_CODES)}|null","district":"ชื่อเขตหรือ null","urgency":"low|medium|high"}}

กฎ:
- intent: complaint=แจ้งปัญหา/เหตุเดือดร้อนในเมือง, inquiry=ถามข้อมูล/ระเบียบ/ขั้นตอนบริการราชการ, unclear=จับใจความไม่ได้
- category ({_CATEGORY_HELP}) ถ้าเป็น inquiry ใส่ null
- sub ({_SUB_HELP}) ถ้าไม่เข้าข่ายใส่ null
- district ต้องเป็นหนึ่งใน 50 เขต: {", ".join(DISTRICTS)} (ไม่ต้องมีคำว่า เขต) ถ้าไม่ระบุหรือไม่แน่ใจใส่ null อย่าเดา
- urgency: high=อันตรายต่อชีวิต/ทรัพย์สิน มีผู้บาดเจ็บ น้ำท่วม ไฟรั่ว เหตุฉุกเฉิน, low=ไม่รีบ, อื่นๆ=medium"""

_FEW_SHOT: list[tuple[str, dict]] = [
    (
        "ท่อน้ำทิ้งหน้าตลาดนัดแตก น้ำไหลท่วมทางเดินเต็มไปหมด คนลื่นล้มเจ็บไปแล้วหนึ่งคน เขตบางพลัด",
        {"intent": "complaint", "category": "other", "sub": "drain", "district": "บางพลัด", "urgency": "high"},
    ),
    (
        "อยากถามว่าย้ายทะเบียนบ้านไปอยู่ที่ใหม่ ต้องแจ้งภายในกี่วันคะ",
        {"intent": "inquiry", "category": None, "sub": None, "district": None, "urgency": "low"},
    ),
    (
        "ผิวถนนหน้าโรงพยาบาลเป็นหลุมลึกหลายจุด ช่วยมาซ่อมด้วยค่ะ แถวเขตราชเทวี",
        {"intent": "complaint", "category": "road", "sub": None, "district": "ราชเทวี", "urgency": "medium"},
    ),
]


def classify_messages(transcript: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": CLASSIFY_SYSTEM}]
    for user_text, answer in _FEW_SHOT:
        messages.append({"role": "user", "content": f"ข้อความ: {user_text}"})
        messages.append({"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)})
    messages.append({"role": "user", "content": f"ข้อความ: {transcript}"})
    return messages


RAG_SYSTEM = (
    "คุณคือ AI เจ้าหน้าที่สายด่วน กทม. 1555 ตอบประชาชนทางโทรศัพท์เป็นภาษาไทยสุภาพ (ลงท้ายค่ะ) "
    "ตอบจาก [ข้อมูลอ้างอิง] เท่านั้น ห้ามแต่งข้อมูลเพิ่ม ตัวเลข วัน เวลา และค่าธรรมเนียมต้องตรงกับข้อมูลอ้างอิง "
    "ตอบสั้นไม่เกิน 3 ประโยค เหมาะกับการอ่านออกเสียง ไม่ใช้สัญลักษณ์หรือรายการหัวข้อ "
    "ถ้าข้อมูลอ้างอิงไม่พอตอบ ให้บอกว่าไม่มีข้อมูลและเสนอโอนสายหาเจ้าหน้าที่"
)


def rag_messages(question: str, context_blocks: list[str]) -> list[dict[str, str]]:
    context = "\n\n".join(f"[{i}] {block}" for i, block in enumerate(context_blocks, start=1))
    return [
        {"role": "system", "content": RAG_SYSTEM},
        {"role": "user", "content": f"[ข้อมูลอ้างอิง]\n{context}\n\n[คำถามประชาชน]\n{question}"},
    ]
