# Implementation Tasks
# BKK CivicConnect AI: Intelligent Omnichannel Citizen Contact Center for Bangkok
**Specification Path:** `.kiro/specs/bkk-civic-connect/tasks.md`

---

## Phase 1: Environment & Mock Data Setup
- [ ] 1.1 สร้าง Virtual Environment และติดตั้ง Dependencies (`fastapi`, `uvicorn`, `pydantic`, `websockets`, `pandas`)
- [ ] 1.2 จัดทำชุดข้อมูลตัวอย่างคำร้องเรียนภาษาไทยจริง 50 ตัวอย่างจาก `opendata/processed/` สำหรับใช้ทดสอบและ Demo

## Phase 2: Core AI Engine & Classification API
- [ ] 2.1 สร้าง FastAPI Server โครงสร้างหลัก (`main.py`)
- [ ] 2.2 สร้างโมดูล `ai_classifier.py` จำลองและต่อเข้ากับ Thai LLM (Typhoon / Gemma Interface)
  - จำแนก Intent (แจ้งปัญหา vs สอบถามบริการ)
  - สกัดหมวดหมู่ (ถนน, ทางเท้า, จราจร, ไฟฟ้า, ขยะ)
  - สกัดเขต 50 เขต กทม. และระดับความเร่งด่วน
- [ ] 2.3 สร้าง REST API Endpoint `/api/v1/civic/classify` และ `/api/v1/tickets`

## Phase 3: Genesys Cloud Integration & Agent Widget
- [ ] 3.1 สร้าง Webhook Endpoint `/api/v1/genesys/webhook` รองรับ Interaction Payload จาก Genesys Cloud CX
- [ ] 3.2 สร้าง WebSocket Gateway `/ws/agent/{interaction_id}` สำหรับ Push Live Transcript และ AI Summary
- [ ] 3.3 พัฒนาหน้าเว็บ **Genesys Agent Interaction Widget** (`frontend/widget.html`) สำหรับ Embed ใน Genesys Workspace

## Phase 4: End-to-End Simulation & Verification
- [ ] 4.1 รัน Test Script จำลองสายโทรเข้าจากประชาชน (Inbound Call Simulation)
- [ ] 4.2 ตรวจสอบการสร้าง Ticket และการแสดงผลบน Agent Widget แบบเรียลไทม์
- [ ] 4.3 จัดเตรียม Live Demo Script และ Backup Video สำหรับวันแข่งขัน
