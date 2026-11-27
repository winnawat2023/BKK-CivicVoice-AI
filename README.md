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

## เริ่มใช้งานและทดสอบ

| หน้าจอ | เปิดและทดลอง |
| --- | --- |
| เว็บประชาชน | [หน้าเว็บ](http://127.0.0.1:8765/) → **ติดต่อเรา** มุมขวาล่าง → **เริ่มสนทนาบนเว็บ** อนุญาตไมค์ ระบบส่งเสียงเมื่อหยุดพูดและขึ้นข้อความตอบหลัง AI พูดจบ กด **จบการสนทนา** เพื่อดูสรุป เลือกเขตจากรายชื่อ 50 เขตหรือแก้รายละเอียดสถานที่ก่อนยืนยัน |
| Agent Copilot | [โต๊ะเจ้าหน้าที่](http://127.0.0.1:8765/desk.html) เลือกสายหรือกรอก Conversation ID เปิด iframe ขนาด 400, 450 หรือ 500px ดู Transcript และสรุปสด ยืนยันส่งเขตเพื่อเปลี่ยนสถานะใน Backend |
| Citizen Tracking | [เดโม Timeline 4 ขั้น](http://127.0.0.1:8765/tracking/?mode=demo) สำหรับคำร้องจริงเปิดจากลิงก์หลังยืนยันหรือจาก SMS เพื่อดูสถานะและเพิ่มหลักฐาน |
| เดโมสำหรับซ้อม | [โต๊ะเจ้าหน้าที่พร้อมข้อมูลตัวอย่าง](http://127.0.0.1:8765/desk.html?mode=demo) และ [Agent Copilot แบบแยก](http://127.0.0.1:8765/widget/?mode=demo) |

รันคำสั่งนี้จาก root ของ branch `feature/fe-widget` เพื่อเปิดหน้าเว็บและเดโมแบบไม่ต้องใช้ Backend

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory src/frontend
```

สำหรับการสนทนาจริงบนเว็บ, WebSocket, ระบบ Genesys และ SMS ให้ทำตาม [วิธีติดตั้ง รัน และทดสอบครบทุกบริการ](docs/runtime-integration.md) ดูสี ฟอนต์ การจัดวาง และภาพใน [คู่มือ Soft Blue](docs/frontend-style-guide.md)

Frontend ใช้ Tailwind CSS ที่คอมไพล์ไว้แล้วและฟอนต์ Sarabun ในโปรเจกต์ หากแก้คลาสให้คอมไพล์ใหม่ด้วย [Tailwind CLI](https://tailwindcss.com/docs/installation/tailwind-cli) รุ่น 4.1.18

```powershell
tailwindcss -i src/frontend/tailwind.input.css -o src/frontend/tailwind.css --minify
```

## SMS หลังยืนยันแจ้งปัญหา

กรอกเบอร์มือถือในหน้าสรุปได้ เมื่อ Backend ออกเลขคำร้องแล้วจึงกด **ส่ง SMS** ข้อความใช้เลขคำร้อง สรุปสั้นจาก AI และพื้นที่จากคำร้องที่บันทึก พร้อมลิงก์เปิดหน้าส่งรูป แชร์ GPS หรือวางลิงก์ Google Maps, Apple Maps และ OpenStreetMap ผู้รับเพิ่มข้อมูลประกอบผ่านหน้าเว็บที่เปิดจาก SMS

โหมด `disabled` ให้ยืนยันคำร้องได้ตามปกติและปิดการส่ง SMS โหมด `mock` บน localhost ให้ทดลองกด **ส่ง SMS** แล้วเปิด **ลิงก์ SMS จำลอง** จากป๊อปอัปได้โดยไม่ใช้เครดิต โหมดจริงรองรับ SMSKUB และ ThaiBulkSMS

**เปิดส่งจริงด้วย ThaiBulkSMS**

1. เปิด `src/backend/sms.env` ในเครื่องและตั้ง `SMS_MODE=thaibulksms` พร้อม `THAIBULKSMS_API_KEY`, `THAIBULKSMS_API_SECRET` และ `THAIBULKSMS_SENDER` จากบัญชีที่มีเครดิตและอนุมัติชื่อผู้ส่งกับโดเมนลิงก์แล้ว ดูรายละเอียดใน [คู่มือ ThaiBulkSMS](https://developer.thaibulksms.com/)
2. ตั้ง `SMS_ALLOWED_RECIPIENTS` เป็นเบอร์มือถือทดสอบของทีม คั่นแต่ละเบอร์ด้วยจุลภาค ตั้ง `SMS_PUBLIC_ORIGIN` เป็น HTTPS ของหน้าเว็บที่มือถือเปิดได้ และตั้ง `SMS_VOICEBOT_ORIGIN` ให้บริการ SMS เข้าถึง Voicebot 2.0 ได้ เก็บไฟล์ `sms.env` ไว้ฝั่งเซิร์ฟเวอร์
3. หลัง HTTPS gateway ให้ใช้ origin เดียวกันกับหน้าเว็บสำหรับ `/api/v1/*` และ `/api/sms/*` เก็บบริการ SMS ไว้ในเครือข่ายส่วนตัว กำหนด `SMS_CONFIRM_SECRET` แบบสุ่มให้บริการ SMS และให้ gateway ลบ `X-SMS-Confirm-Secret` ที่ส่งมาจากฝั่งผู้ใช้ แล้วเพิ่ม header นี้เฉพาะคำขอ `/api/sms/confirm` ที่ผ่านการตรวจสิทธิ์ เปิด `deployment.enableCitizenVoice` ใน `src/frontend/config.mjs` เมื่อ gateway พร้อม แล้วเปิดหน้า `/?mode=live`
4. รันบริการ SMS ใหม่ ยืนยันคำร้องจากมือถือทดสอบและส่ง SMS หนึ่งครั้ง หลังผู้ให้บริการรับคำขอ หน้าเว็บจะแสดงสถานะรับคำขอส่ง ให้ตรวจการได้รับจริงและการเปิดลิงก์บนมือถือแยกกัน

**เปิดส่งจริงด้วย SMSKUB**

1. สร้าง API Key จาก Console ของ SMSKUB แล้วตรวจชื่อผู้ส่งด้วย `GET /api/senders/usable` และยอดเครดิตด้วย `GET /api/transactions/balance` ที่ `https://console.sms-kub.com` ใช้ header `key` ตาม Postman Collection ซึ่งทดสอบกับคีย์จาก Console แล้ว [Postman Collection](https://documenter.getpostman.com/view/9887776/2sAYXCjyAF)
2. ตั้ง `SMS_MODE=smskub`, `SMSKUB_API_KEY` และ `SMSKUB_SENDER` ในไฟล์ `src/backend/sms.env` จากนั้นตั้ง `SMS_ALLOWED_RECIPIENTS`, `SMS_PUBLIC_ORIGIN`, `SMS_VOICEBOT_ORIGIN` และ `SMS_CONFIRM_SECRET` พร้อม HTTPS gateway ตามขั้นตอนด้านบน โดย URL สำหรับลิงก์เพิ่มเติมต้องผ่านการอนุมัติคู่กับชื่อผู้ส่ง [เงื่อนไข URL ของ SMSKUB](https://sms-kub.com/faq/)
3. รีสตาร์ตบริการ SMS แล้วทดสอบจาก Widget หลังยืนยันคำร้อง บริการใช้ Quick Send `POST /api/messages` และตรวจ `code`, `data.send` และ `data.block` ก่อนแสดงว่ารับคำขอ ตัวอย่าง Postman แสดงว่า HTTP 200 อาจมาพร้อมผลปลายทางถูกบล็อกหรือเครดิตไม่พอ และ Quick Send อาจคืนเฉพาะจำนวนข้อความโดยไม่มี message ID [Postman Collection](https://documenter.getpostman.com/view/9887776/2sAYXCjyAF)

ลิงก์สำหรับส่งหลักฐานหมดอายุใน 7 วัน ระบบจำกัดหนึ่งคำขอ SMS ต่อคำร้องและมีเพดานต่อวัน ข้อมูลจัดเก็บตามเลขคำร้องใน SQLite ที่ `SMS_DB_PATH` ค่าเริ่มต้นแยกไฟล์ตามโหมดใน `data/` ทีม Backend สามารถอ่านผ่าน `GET /api/sms/admin/evidence/{ticket_id}` และ `GET /api/sms/admin/evidence/{ticket_id}/photo` โดยส่ง `Authorization: Bearer <SMS_ADMIN_TOKEN>` จากฝั่งเซิร์ฟเวอร์เท่านั้น การแนบข้อมูลกลับเข้า Core Backend ต้องเชื่อมเพิ่มเมื่อมี API รับข้อมูลประกอบคำร้อง
