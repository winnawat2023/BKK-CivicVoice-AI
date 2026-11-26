# BKK CivicVoice AI: AI-First Omnichannel Citizen Contact Center for Bangkok
> **AI Skill Wars 2026 : AI For Bangkok (Hackathon)**  
> **Theme 02:** Civic & Public Service Access (บริการภาครัฐและข้อมูลเมือง)  
> **Team:** ARK Insights Co., Ltd. (`ark-insights`)

---

## 🌟 Executive Summary
**BKK CivicVoice AI** ยกระดับศูนย์บริการข้อมูลและรับเรื่องร้องทุกข์ของกรุงเทพมหานคร (สายด่วน กทม. 1555) ให้เป็น **AI-First Contact Center** เพื่อให้ประชาชนทุกกลุ่ม (โดยเฉพาะผู้สูงอายุและผู้กำลังสัญจร) เข้าถึงบริการรัฐได้อย่างเท่าเทียมผ่าน "เสียงพูดภาษาไทยธรรมชาติ" 

ระบบขับเคลื่อนด้วย **Genesys Cloud CX**, **Thai LLM (Typhoon / Fine-tuned Gemma)** และพัฒนาภายใต้ระเบียบวิธี **AI-DLC (AI-Driven Development Life Cycle) บน Kiro IDE**

---

## 👥 Team Members & Roles (ARK Insights)
* **Mr. Chaiyaporn Homtean** (`h.chaiyaporn@ark-insights.com`) — Team Lead & Pitch Master
* **Mr. Watchara Bangkerdlap** (`b.watchara@ark-insights.com`) — Genesys Cloud CX & Telephony Engineer
* **Mr. Peerapun Sinyu** (`s.peerapun@ark-insights.com`) — AI Engine & Data Engineer
* **Mr. Aitthiphon Puangsupan** (`p.aitthiphon@ark-insights.com`) — Frontend Widget & Real-time Integration

---

## 🏗️ System Architecture

```
[ ประชาชน (Citizen Touchpoint) ]
     │
     ├── 📞 Voice Call (PSTN / เบอร์สายด่วน กทม. 1555 จำลอง)
     └── 💬 Digital Messaging (Web Chat / LINE)
               │
               ▼
   [ Genesys Cloud CX Platform (Org: ark-insights) ]
     ├── Architect IVR & ACD Inbound Routing
     ├── AudioHook / Webhook Integration
     └── Agent Workspace (Custom Interaction Widget)
               │
               ▼ (Webhook / WebSocket)
   [ BKK CivicVoice AI Core Middleware (FastAPI) ]
     ├── 1. Speech-to-Text (Thai Audio Ingestion)
     ├── 2. Thai LLM Reasoning (Typhoon / Gemma):
     │      ├── Intent Classifier (สอบถามข้อมูลบริการ vs. แจ้งเรื่องร้องเรียน)
     │      ├── Entity Extractor (หมวดหมู่, พิกัดสถานที่, 50 เขต, ความเร่งด่วน)
     │      └── Civic RAG Service (คู่มือระเบียบ กทม.)
     └── 3. WebSocket Real-time Gateway
               │
               ▼
   [ Live Operations & Target Systems ]
     ├── 🤖 Auto Voice Response (ตอบระเบียบราชการจบในสาย 0 วินาที)
     ├── 🎫 Auto Create Civic Ticket (ส่งเรื่องเข้าเขตอัตโนมัติ)
     └── 🖥️ Genesys Agent Widget (Live Transcript & 3-Bullet Summary)
```

---

## 📁 Project Structure

```text
├── docs/                      # เอกสารข้อกำหนดและการวิเคราะห์
│   ├── requirements.md        # PRD / Functional Specifications
│   ├── team-roles.md          # โครงสร้างบทบาทของทีม
│   ├── battle-plan-timeline.md# แผนยุทธศาสตร์เวลา 23-30 พ.ย.
│   ├── work-assignment.md     # รายละเอียดการมอบหมายงานรายคน
│   └── 1555-analysis-and-gap.md # ข้อมูลเชิงลึกและการทำงานของสายด่วน 1555
├── opendata/                  # คลังข้อมูลเปิด กทม. (BKK Open Data)
│   ├── catalog/               # ดัชนีชุดข้อมูลทั้งหมดของ กทม. (1,531 รายการ)
│   └── processed/             # ผลการวิเคราะห์สถิติปัญหาเมืองย้อนหลัง 3 ปี (8.85 แสนเคส)
├── src/
│   ├── backend/               # FastAPI Backend Middleware
│   │   ├── main.py            # Core REST API + WebSocket Server
│   │   └── requirements.txt   # Python Dependencies
│   ├── asr/                   # ASR Service (Faster-Whisper, พอร์ต 5001) ดู docs/asr-service.md
│   │   ├── main.py            # Entry point
│   │   └── asr_service/       # REST /v1/transcribe + WebSocket /v1/stream/{id}
│   ├── frontend/
│   │   └── widget/            # Genesys Agent Interaction Widget (Tailwind CSS)
│   └── tests/
│       └── simulate_call.py   # End-to-End Inbound Call Simulation
└── .kiro/specs/               # Kiro Spec-driven Development (requirements, design, tasks)
```

---

## 🚀 Quick Start (Local Setup)

### 1. ติดตั้ง Dependencies ฝั่ง Backend
```bash
cd src/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. รัน Core Middleware
```bash
python3 main.py
# Server will start on http://localhost:8000
# OpenAPI Docs: http://localhost:8000/docs
```

### 3. เปิดหน้าจอ Genesys Agent Widget
เปิดไฟล์ `src/frontend/widget/index.html` บนเว็บเบราว์เซอร์ เพื่อดูหน้าจอ Agent Copilot แบบเรียลไทม์

### 4. ทดสอบจำลองสายโทรเข้า (Simulation)
```bash
python3 src/tests/simulate_call.py
```

### 5. รัน ASR Service (ถอดเสียงด้วย Faster-Whisper)
บริการแยกจาก Middleware ใช้ venv ของตัวเอง ครั้งแรกจะดาวน์โหลดโมเดลจาก Hugging Face
```bash
cd src/asr
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 5001
# ส่งไฟล์เสียงเข้า Middleware: curl -F "file=@call.wav" -F "interaction_id=CALL-1" http://localhost:5001/v1/transcribe
```
เครื่องที่ไม่มี GPU ให้ตั้ง `ASR_MODEL=small` ก่อนรัน รายละเอียด API, WebSocket เสียงสด และข้อจำกัด ดู [docs/asr-service.md](docs/asr-service.md)
