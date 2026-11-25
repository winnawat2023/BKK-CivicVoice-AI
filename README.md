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

ดู [คู่มือสไตล์ Soft Blue และภาพหน้าจอต้นแบบ](docs/frontend-style-guide.md) เอกสารรอบนี้อ้างอิงต้นแบบจาก working copy ของทีม การรันหน้า `/`, `/desk.html`, `/tracking/` และบริการ SMS ต้องใช้ซอร์สต้นแบบจากเครื่องพัฒนาหรือจาก commit โค้ดที่จะเผยแพร่ภายหลัง

จาก root ของ repository ให้เปิดเซิร์ฟเวอร์สำหรับไฟล์ Frontend:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory src/frontend
```

- หน้า AI Voice สำหรับประชาชน: `http://127.0.0.1:8765/` กด **ติดต่อเรา** แล้วลองแจ้งปัญหา ดูสรุป ยืนยัน และเปิด Tracking ของคำร้องตัวอย่าง
- โต๊ะเจ้าหน้าที่: `http://127.0.0.1:8765/desk.html` เลือกสายตัวอย่างและทดลองรับสาย เพิ่มข้อความ ส่งเรื่อง หรือจบสาย Agent Copilot แสดงเป็น iframe ด้านข้าง ปรับขนาดได้ 400/450/500px
- เมื่อ Backend 2.0 รันที่พอร์ต 8000 ให้เปิด `http://127.0.0.1:8765/?mode=live` เพื่อทดสอบ AI Voice กับ API Guide การใช้ไมค์ต้องอาศัยเบราว์เซอร์ที่รองรับ SpeechRecognition และ origin ที่เปิดสิทธิ์ไมค์ได้
- Agent Copilot แบบเปิดแยก: `http://127.0.0.1:8765/widget/?mode=demo`
- Citizen Tracking เดโม: `http://127.0.0.1:8765/tracking/?mode=demo`
- เชื่อม API 2.0 local: `http://127.0.0.1:8765/widget/?interaction_id=CALL-9042-DEMO&apiBase=http://127.0.0.1:8000`
- ดูคำร้องภายใน: `http://127.0.0.1:8765/tracking/?mode=internal&ticket=BKK-2026-0001&apiBase=http://127.0.0.1:8000`

เมื่อนำไปฝังใน Genesys ให้ตั้งค่า API origin ใน `src/frontend/config.mjs` และส่ง Conversation ID มาที่ Widget โดยตามค่าเริ่มต้น API origin จะมาจาก origin ของหน้า Frontend ดูขั้นเปิดใช้และบริการที่ยังต้องรอใน [แผนเชื่อม API 2.0](aidlc/spaces/default/intents/261120-civic-contact-center/inception/refined-mockups/frontend-widget-proposal/frontend-api-integration-plan.md)

หน้าเดโมใช้ Tailwind CSS ที่คอมไพล์ไว้แล้วกับฟอนต์ Sarabun ในโปรเจกต์ หากแก้คลาส Tailwind ให้คอมไพล์ใหม่ด้วย [Tailwind CLI](https://tailwindcss.com/docs/installation/tailwind-cli) รุ่น 4.1.18:

```bash
tailwindcss -i src/frontend/tailwind.input.css -o src/frontend/tailwind.css --minify
```

### 4. ทดสอบจำลองสายโทรเข้า (Simulation)
```bash
python3 src/tests/simulate_call.py
```

### 5. SMS หลังยืนยันแจ้งปัญหา

หน้าเดโมที่ `http://127.0.0.1:8765/` เปิดลิงก์จำลองได้ทันที หลังคุยกับ AI Voice และกด **ยืนยันแจ้งปัญหา** ให้เลือก **ส่ง SMS ให้ประชาชนปักหมุด GPS / แนบรูปถ่าย** ลิงก์จำลองแบบนี้ใช้ดูหน้าตาและทดลองปุ่มได้โดยไม่ส่งข้อความหรือบันทึกข้อมูลลงเซิร์ฟเวอร์

สำหรับทดสอบบันทึกข้อมูลจริงโดยไม่ใช้เครดิต ให้รัน Backend ตาม API Guide 2.0 ที่พอร์ต 8000 แล้วรันบริการ SMS แยกจาก root ของ repository ด้วย PowerShell

```powershell
python -m pip install -r src/backend/requirements-sms.txt
Copy-Item src/backend/sms.env.example src/backend/sms.env
python -m uvicorn sms_evidence:application --factory --app-dir src/backend --host 127.0.0.1 --port 8766
```

เปิด `http://127.0.0.1:8765/?mode=live` โดยใช้ `SMS_MODE=mock` ตามตัวอย่าง เมื่อ Voicebot ยืนยันเลขคำร้องแล้ว ปุ่ม SMS จะสร้างลิงก์ของคำร้องนั้น กดอนุญาตตำแหน่ง ตรวจพิกัดและกดยืนยัน หรือเลือกรูป JPEG, PNG หรือ WebP ไม่เกิน 5 MB และกดยืนยันอัปโหลด

**เปิดส่งจริงด้วย ThaiBulkSMS**

1. เปิด `src/backend/sms.env` ในเครื่องและตั้ง `SMS_MODE=thaibulksms` พร้อม `THAIBULKSMS_API_KEY`, `THAIBULKSMS_API_SECRET` และ `THAIBULKSMS_SENDER` จากบัญชีที่มีเครดิตและอนุมัติชื่อผู้ส่งกับโดเมนลิงก์แล้ว ดูรายละเอียดใน [คู่มือ ThaiBulkSMS](https://developer.thaibulksms.com/)
2. ตั้ง `SMS_ALLOWED_RECIPIENTS` เป็นเบอร์มือถือทดสอบของทีม คั่นแต่ละเบอร์ด้วยจุลภาค ตั้ง `SMS_PUBLIC_ORIGIN` เป็น HTTPS ของหน้าเว็บที่มือถือเปิดได้ และตั้ง `SMS_VOICEBOT_ORIGIN` ให้บริการ SMS เข้าถึง Voicebot 2.0 ได้ เก็บไฟล์ `sms.env` ไว้ฝั่งเซิร์ฟเวอร์
3. หลัง HTTPS gateway ให้ใช้ origin เดียวกันกับหน้าเว็บสำหรับ `/api/v1/*` และ `/api/sms/*` เก็บบริการ SMS ไว้ในเครือข่ายส่วนตัว กำหนด `SMS_CONFIRM_SECRET` แบบสุ่มให้บริการ SMS และให้ gateway ลบ `X-SMS-Confirm-Secret` ที่ส่งมาจากฝั่งผู้ใช้ แล้วเพิ่ม header นี้เฉพาะคำขอ `/api/sms/confirm` ที่ผ่านการตรวจสิทธิ์ เปิด `deployment.enableCitizenVoice` ใน `src/frontend/config.mjs` เมื่อ gateway พร้อม แล้วเปิดหน้า `/?mode=live`
4. รันบริการ SMS ใหม่ ยืนยันคำร้องจากมือถือทดสอบและส่ง SMS หนึ่งครั้ง หลังผู้ให้บริการรับคำขอ หน้าเว็บจะแสดงสถานะรับคำขอส่ง ให้ตรวจการได้รับจริงและการเปิดลิงก์บนมือถือแยกกัน

ลิงก์สำหรับส่งพิกัดหรือรูปหมดอายุใน 7 วัน ระบบจำกัดหนึ่งคำขอ SMS ต่อคำร้องและมีเพดานต่อวัน ข้อมูลจัดเก็บตามเลขคำร้องใน SQLite ที่ `SMS_DB_PATH` ค่าเริ่มต้นแยกไฟล์ตามโหมดใน `data/` ทีม Backend สามารถอ่านผ่าน `GET /api/sms/admin/evidence/{ticket_id}` และ `GET /api/sms/admin/evidence/{ticket_id}/photo` โดยส่ง `Authorization: Bearer <SMS_ADMIN_TOKEN>` จากฝั่งเซิร์ฟเวอร์เท่านั้น การแนบข้อมูลกลับเข้า Core Backend ต้องเชื่อมเพิ่มเมื่อมี API รับข้อมูลประกอบคำร้อง
