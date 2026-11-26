# Project Requirement Document (PRD)
## BKK CivicVoice AI: Intelligent Omnichannel Citizen Contact Center for Bangkok
**AI Skill Wars 2026 — Theme 02: Civic & Public Service Access**  
**Team / Organization:** ARK Insights Co., Ltd. (`ark-insights`)  
**Core Technologies:** Kiro IDE + AI-DLC, Genesys Cloud CX, Faster-Whisper (large-v3-turbo), Typhoon-1.5X-8B-Instruct, FastAPI/Python, WebSocket

### Team Members & Roles:
* **Mr. Chaiyaporn Homtean** (`h.chaiyaporn@ark-insights.com`) — Member 1: Team Lead, Product & Pitch Master
* **Mr. Watchara Bangkerdlap** (`b.watchara@ark-insights.com`) — Member 2: Genesys Cloud CX & Telephony Engineer
* **Mr. Peerapun Sinyu** (`s.peerapun@ark-insights.com`) — Member 3: AI Engine & Data Engineer
* **Mr. Aitthiphon Puangsupan** (`p.aitthiphon@ark-insights.com`) — Member 4: Frontend Widget & Real-time Integration

---

## 1. Executive Summary & Problem Statement

### 1.1 The Urban Problem (Pain Point ในกรุงเทพมหานคร)
* **ปัญหาช่องทางการติดต่อประชาชน (1555 & สายด่วน กทม.):** ประชาชนจำนวนมาก (โดยเฉพาะผู้สูงอายุและคนทั่วไป) ไม่สะดวกพิมพ์แจ้งผ่านแอปพลิเคชัน (เช่น Traffy Fondue) แต่นิยม **"โทรศัพท์เข้าศูนย์บริการ 1555"**
* **ภาระงานเจ้าหน้าที่สูง (High Call Volume & Repetitive Enquiries):** มีสายโทรเข้ามาสอบถามข้อมูลขั้นตอนราชการซ้ำๆ เช่น การต่อทะเบียนราษฎร์, ขั้นตอนขอบ้านเลขที่, สิทธิการรักษา ทำให้คู่สายเต็ม ประชาชนรอนาน
* **การบันทึกเรื่องร้องเรียนตกหล่น (Manual & Unstructured Logging):** การฟังเสียงพูดของประชาชนแล้วคีย์ข้อมูลด้วยมือทำให้ข้อมูลสถานที่, รายละเอียดความเร่งด่วน ผิดพลาดหรือไม่ครบถ้วน

### 1.2 The Solution
**BKK CivicConnect AI** คือระบบ Contact Center ภาครัฐอัจฉริยะที่เชื่อมโยง **Genesys Cloud CX** เข้ากับ **Thai LLM (Typhoon / Gemma)** โดยใช้ **AI-DLC on Kiro** ในการพัฒนา มี 2 ฟังก์ชันหลัก:
1. **AI Voice & Chat Bot (First-line Automation):** รับสายเสียงพูดภาษาไทยธรรมชาติ ตอบข้อซักถามระเบียบ กทม. ได้ทันที หรือหากเป็นการแจ้งเรื่องร้องเรียน ระบบจะสกัด Entity (หมวดหมู่, สถานที่, ความรุนแรง) แล้วสร้าง Ticket เข้าสู่ระบบโดยอัตโนมัติ
2. **AI Copilot for Contact Center Agent (Genesys Interaction Widget):** กรณีสายถูกโอนมาหาเจ้าหน้าที่มนุษย์ หน้าจอ Genesys Desktop จะแสดง Live Audio Transcript ภาษาไทย, AI Summary 3 บรรทัด, และข้อเสนอแนะขั้นตอนการให้บริการ (Next Best Action) ช่วยลดเวลาสนทนา (AHT) ได้มากกว่า 60%

---

## 2. Competitive Advantage (จุดแข็งเฉพาะของ ARK Insights)
* **Enterprise Infrastructure Ready:** ใช้งาน **Genesys Cloud CX Org (`ark-insights`)** พร้อม Architect Inbound Call Flows และ Webhook Integration ทันที ไม่ใช่แค่ Mock Web Form
* **Thai-Native Domain AI:** มีโมเดล **Typhoon** และ **Gemma** ที่ Fine-tune คำศัพท์เฉพาะภาษาไทย (เขต กทม., หน่วยงานรัฐ, สำนวนภาษาพูดร้องเรียน)
* **Structured Development with AI-DLC:** พัฒนาตามกระบวนการ Inception → Construction บน Kiro IDE ทำให้มี Architecture, Test Cases และ Verification ที่โปร่งใสและตรวจสอบได้

---

## 3. System Architecture & Component Design

```
[ Citizen (Citizen Touchpoint) ]
     │
     ├── 📞 Voice Call (PSTN / WebRTC)
     └── 💬 Digital Messaging (Web Chat / LINE)
               │
               ▼
   [ Genesys Cloud CX Platform (Org: ark-insights) ]
     ├── Architect IVR & ACD Inbound Routing
     ├── AudioHook / Media Streaming API (Voice RTP Stream)
     └── Agent Workspace (Custom Interaction Widget iframe)
               │
               ▼ (Webhook / WebSocket Event)
   [ BKK CivicConnect Core Middleware (Built via Kiro & AI-DLC) ]
     ├── 1. Speech-to-Text / Audio Ingestion (Thai STT Engine)
     ├── 2. Thai LLM Reasoning Core (Typhoon / Gemma):
     │      ├── Intent Classifier (สอบถามข้อมูลบริการ vs. แจ้งเรื่องร้องเรียน)
     │      ├── Entity Extractor (ประเภทปัญหา, เขต/พิกัด, ระดับความเร่งด่วน)
     │      └── Civic RAG Service (คู่มือประชาชน กทม. 50 เขต)
     ├── 3. Civic Ticket Management API (FastAPI)
     └── 4. Agent Assist WebSocket Gateway
               │
               ▼
   [ Live Operations & Target Systems ]
     ├── 🤖 Auto Voice Synthesis (TTS ตอบประชาชนจบในสาย)
     ├── 🎫 BKK Civic Issue Ticket Database (RESTful API / JSON Store)
     └── 🖥️ Genesys Agent Widget (Real-time Live Transcript & Copilot Panel)
```

---

## 4. User Stories & Acceptance Criteria

### User Story 1: ประชาชนโทรสอบถามข้อมูลราชการ กทม. (Automated Q&A Flow)
* **As a:** ประชาชนชาวกรุงเทพฯ
* **I want to:** โทรเข้ามาสอบถามขั้นตอนการทำบัตรประชาชน หรือการขอทะเบียนบ้าน ด้วยภาษาพูดปกติ
* **So that:** ผมได้รับคำตอบทันทีโดยไม่ต้องถือสายรอเจ้าหน้าที่
* **Acceptance Criteria (AC):**
  1. ระบบรับสายผ่าน Genesys Cloud Inbound Call
  2. STT และ Thai LLM เข้าใจ Intent ประเภท "สอบถามข้อมูลบริการ"
  3. AI ตอบกลับด้วยข้อมูลที่ถูกต้องจากฐานข้อมูลระเบียบ กทม. (RAG) ภายใน 2 วินาที

### User Story 2: ประชาชนโทรแจ้งปัญหาเมือง (Auto-Ticket Generation Flow)
* **As a:** ประชาชนผู้พบเห็นปัญหาในพื้นที่กรุงเทพฯ
* **I want to:** โทรแจ้งเหตุ เช่น "ท่อระบายน้ำแตก น้ำท่วมซอยสุขุมวิท 50 อันตรายมาก"
* **So that:** ระบบรับเรื่อง บันทึกตำแหน่ง และส่งให้ฝ่ายที่เกี่ยวข้องทันที
* **Acceptance Criteria (AC):**
  1. AI แยกแยะว่าเป็น Intent "แจ้งปัญหาเมือง (Civic Incident)"
  2. Entity Extraction ดึงข้อมูล:
     * `Category`: ท่อระบายน้ำ/น้ำท่วม (สุขาภิบาล/โยธา)
     * `Location`: ซอยสุขุมวิท 50 (เขตคลองเตย)
     * `Severity`: High (มีคำว่า "อันตรายมาก/ท่อแตก")
  3. สร้าง Ticket ในระบบอัตโนมัติพร้อมออก Ticket ID (เช่น `BKK-2026-XXXX`) และส่ง SMS/Message ยืนยัน

### User Story 3: เจ้าหน้าที่รับสายพร้อม AI Copilot บน Genesys Cloud (Agent Assist)
* **As a:** เจ้าหน้าที่ศูนย์บริการ 1555 บน Genesys Cloud
* **I want to:** เห็นสรุปเรื่อง ปัญหา และข้อเสนอแนะในการตอบบนหน้าจอ Interaction Widget แบบเรียลไทม์
* **So that:** ผมสามารถช่วยเหลือประชาชนได้รวดเร็ว ถูกต้อง และปิดสายได้ในเวลารวดเร็ว
* **Acceptance Criteria (AC):**
  1. เมื่อสายโอนมาถึง Agent หน้าจอ Genesys Widget จะแสดง Live Transcript ภาษาไทย
  2. แสดงกล่อง AI Summary (3 Key Points) สรุปจากสิ่งที่ประชาชนพูด
  3. แสดง Suggested Responses / Action (เช่น แนะนำระเบียบ, ปุ่มกดส่ง Ticket ต่อให้สำนักงานเขต)

---

## 5. Scope of Work for Hackathon Prototype (1-Day Implementation Scope)

เพื่อให้พร้อมสำหรับ **Live Demo 30 พฤศจิกายน 2569** ภายในเวลาแข่งขัน 1 วัน:

### Phase 1: Inception & Core Contracts (เสร็จสมบูรณ์ช่วงเช้า)
- [x] กำหนด Architecture, OpenAPI Schema สำหรับ Middleware API
- [x] นิยาม JSON Schema สำหรับการแลกเปลี่ยนข้อมูลระหว่าง Genesys Webhook และ AI-DLC Engine
- [x] รวบรวม Sample Prompts และชุดข้อมูลตัวอย่างปัญหาเมือง กทม. (Mock Civic Dataset)

### Phase 2: Construction (พัฒนาด้วย Kiro + AI-DLC)
- [ ] **Backend Service (FastAPI):**
  - Endpoint `/api/v1/voice/webhook`: รับ Event & Transcript จาก Genesys
  - Endpoint `/api/v1/civic/classify`: ส่งข้อความเข้า Typhoon/Gemma เพื่อจัดหมวดหมู่และสกัด Entity
  - Endpoint `/api/v1/tickets`: บันทึกและดึงข้อมูลสถานะ Ticket
- [ ] **AI Reasoning Module:**
  - Prompt Engineering บน Typhoon / Gemma พร้อม Structured Output (JSON Schema Mode)
- [x] **ASR Service (Faster-Whisper large-v3-turbo, พอร์ต 5001):** ถอดเสียงไทย/อังกฤษจากไฟล์ (`POST /v1/transcribe`) และเสียงสด (`WS /v1/stream/{interaction_id}`) แล้วส่งต่อ `/api/v1/calls/{id}/segments` ดู [asr-service.md](asr-service.md) *(ยังไม่เชื่อม Genesys AudioHook และยังไม่วัดความแม่นยำบนเสียงสายจริง)*
- [ ] **Frontend Interaction Widget (HTML/JS/Tailwind):**
  - หน้าต่าง iframe สำหรับฝังใน Genesys Cloud Workspace (Client Application Widget)
  - เชื่อมต่อ WebSocket แสดง Live Transcription, AI Summary และสถานะ Ticket

---

## 6. Demo Script (ลำดับการสาธิตหน้าคณะกรรมการ)

1. **เปิดตัว (1 นาที):** แสดงหน้าจอสถาปัตยกรรมชี้ให้เห็นว่าระบบต่อกับ Genesys Cloud CX จริง
2. **Live Test 1 - สายโทรศัพท์จริง (2 นาที):**
   * โทรศัพท์เข้าเบอร์ทดสอบของ Genesys Cloud
   * พูดแจ้งเหตุ: *"แจ้งทางเท้าชำรุด มีกระเบื้องแตกหน้าร้านสะดวกซื้อ ปากซอยอารีย์ คนสะดุดล้มบ่อยครับ"*
   * แสดงเสียง AI ตอบกลับรับเรื่อง และแสดง Ticket ที่ถูกสร้างขึ้นทันทีในระบบ
3. **Live Test 2 - หน้าจอ Agent Desktop (1.5 นาที):**
   * โอนสายเข้า Agent Desktop ใน Genesys Cloud
   * ส่องหน้าจอ Widget: แสดง Live Thai Transcript + สรุปปัญหา + หน่วยงานรับผิดชอบ (สำนักงานเขตพญาไท)
4. **สรุปคุณค่า & Business Impact (30 วินาที):**
   * ลดเวลาถือสายประชาชน (Queue Waiting Time) ลง 70%
   * ประหยัดเวลางานเอกสารของเจ้าหน้าที่ กทม.
   * เพิ่มความเท่าเทียมให้ผู้สูงอายุและประชาชนทุกกลุ่มเข้าถึงบริการรัฐได้ 24 ชั่วโมง
