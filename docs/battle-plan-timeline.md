# แผนยุทธศาสตร์การพัฒนาและการแข่งขัน: BKK CivicVoice AI
**ทีม / องค์กร:** ARK Insights Co., Ltd. (`ark-insights`)  
**เป้าหมาย:** พัฒนาระบบให้เสร็จสมบูรณ์ 100% พร้อม Demo ภายใน **28 พฤศจิกายน 2569** (ก่อนวันแข่ง 2 วัน) เพื่อรองรับโจทย์ Surprise Brief ในวันแข่งจริง (30 พ.ย. 2569)

---

## 1. การบริหารเวลาและ Milestone สำคัญ (23 – 30 พ.ย. 2569)

```
[ 23-25 พ.ย. ]  --->  [ 26-27 พ.ย. ]  --->  [ 28-29 พ.ย. ]  --->  [ 30 พ.ย. วันแข่งจริง ]
Phase 1 & 2            Phase 3                 Phase 4                 Surprise Challenge
Core AI Engine         Genesys Integration     End-to-End Test         รับโจทย์ลับเพิ่ม 1 ข้อ
& API Backend          & Agent Widget          & Record Video          Plug-in ฟีเจอร์ทันที
```

| วันที่ | เฟสงาน | รายละเอียดงานและเป้าหมาย | ผู้รับผิดชอบ | สถานะ |
| :---: | :--- | :--- | :--- | :---: |
| **23 พ.ย.** | **Phase 1: Architecture & Data Analysis** | • วิเคราะห์ข้อมูลสถิติ 3,012,468 เคส กทม. (2565–2569)<br>• คัดเลือก AI Model Stack (Faster-Whisper Turbo + Typhoon 8B)<br>• ร่าง Pitch Deck 8 สไลด์ & System Flow Infographic | **Chaiyaporn (M1)** | **DONE 100%** |
| **23 – 24 พ.ย.** | **Phase 2: AI Core & Server Deployment** | • Deploy FastAPI Gateway + SSL `voiceai-demo.ark-insights.com`<br>• Deploy Faster-Whisper Turbo บน DGX 101<br>• Deploy Typhoon-1.5X-8B บน vLLM (พอร์ต 8001)<br>• ทดสอบยิง Webhook & Live Inference ภาษาไทย/อังกฤษ ผ่าน 100% | **Peerapun (M3)** | **DONE 100%** |
| **25 – 27 พ.ย.** | **Phase 3: Genesys & Widget UI** | • สร้าง Inbound Call Flow บน Genesys Cloud CX (`ark-insights`) เบอร์ `02-096-6763`<br>• พัฒนาหน้าเว็บ Interaction Widget (Multilingual Copilot + Live Subtitles)<br>• ฝัง Widget ลงใน Genesys Agent Workspace | **Watchara (M2)**<br>**Aitthiphon (M4)** | **IN PROGRESS** |
| **28 พ.ย.** | **Phase 4: Full Integration & Testing** | • ทดสอบ End-to-End: โทรเข้าเบอร์จริง `02-096-6763` → ถอดเทปเสียง → บอทสรุป/ส่งเรื่อง → เด้งขึ้นหน้าจอ Agent Widget<br>• ตรวจสอบเสถียรภาพและความเร็ว (Response Time < 1 วินาที) | **ทีมงานทุกคน** | **PENDING** |
| **29 พ.ย.** | **Rehearsal & Deliverables Freeze** | • จัดทำ Pitch Deck 8 สไลด์ฉบับสมบูรณ์<br>• ถ่ายทำและตัดต่อ **Backup Video (< 3 นาที)**<br>• ซักซ้อมคิวพูด Live Demo ทุกบทบาท | **Chaiyaporn (M1)** | **PENDING** |
| **30 พ.ย.** | **Game Day @ BITEC Buri** | • 09:45 น. รับโจทย์ลับเพิ่ม 1 ข้อ (Surprise Challenge)<br>• 10:00 – 14:30 น. ปรับโค้ดและทดสอบเพิ่ม 1 ฟีเจอร์<br>• 14:30 น. ส่งมอบผลงานทั้งหมด<br>• 15:00 น. ขึ้นเวที Live Demo | **ทีมงานทุกคน** | **GAME DAY** |

---

## 2. กลยุทธ์การรับมือ "โจทย์ลับเพิ่ม 1 ข้อ" ในวันแข่ง (Surprise Challenge Readiness)

ใน Hackathon ระดับโปร มักจะมีการปล่อยโจทย์เซอร์ไพรส์ตอนพิธีเปิด (09:45 น.) เช่น:
* *แนวทาง A (Special Persona):* "ต้องรองรับนักท่องเที่ยวต่างชาติ (Multilingual EN/CN)" หรือ "ต้องรองรับเด็ก/ผู้พิการ"
* *แนวทาง B (Special Channel/Format):* "ต้องส่งแจ้งเตือนเข้า SMS หรือ LINE อัตโนมัติ" หรือ "ต้องสรุปรายงานส่งผู้บริหาร กทม."
* *แนวทาง C (Urgent Incident):* "กรณีเกิดเหตุภัยพิบัติฉุกเฉิน (ไฟไหม้/น้ำท่วมใหญ่) ต้องมีโหมด Broadcast ด่วน"

### 🛡️ สถาปัตยกรรมแบบ Modular เพื่อให้เสียบโจทย์ใหม่ได้ใน 1-2 ชั่วโมง:
1. **API Middleware เป็น Plug-in Architecture:**
   * แยก Endpoint `/api/v1/civic/classify` และ `/api/v1/tickets` ออกจากกันชัดเจน
   * หากโจทย์ลับสั่งเพิ่มเงื่อนไข เพียงแค่เพิ่ม System Prompt ในโมดูล LLM หรือเพิ่ม Logic ใน Adapter Function โดยไม่ต้องรื้อระบบโทรศัพท์หรือ Widget
2. **Genesys Architect Flow ยืดหยุ่นสูง:**
   * ตั้งค่า Switch/Decision Node ใน Genesys Call Flow ไว้ล่วงหน้า สามารถเพิ่มกิ่งเงื่อนไขใหม่ได้ทันทีผ่าน Web Interface โดยไม่ต้อง Deploy โค้ดใหม่
3. **Agent Widget เป็น Dynamic Component:**
   * ออกแบบให้หน้าจอ Widget ดึง Layout และปุ่ม Action ตาม JSON Payload ที่ Backend ส่งมาทาง WebSocket หากมีฟีเจอร์ใหม่ สามารถเพิ่มปุ่มกดได้จาก Backend ทันที

---

## 3. สิ่งที่ต้องส่งมอบในวันแข่งจริง (Submission Checklist - ส่งก่อน 14:30 น.)

| รายการ | เกณฑ์กำหนด | แผนการเตรียม |
| :--- | :--- | :--- |
| **1. Working Prototype** | รันได้จริง ไม่ล่มระหว่างสาธิต | พร้อมตั้งแต่ 28 พ.ย. โดยวันที่ 30 พ.ย. แค่เสียบโจทย์ลับเพิ่ม |
| **2. GitHub Repository** | Public หรือเปิดสิทธิ์ให้กรรมการ | มีโครงสร้างโฟลเดอร์ Clean Code, Dockerfile, และ README พร้อม |
| **3. Pitch Deck** | ไม่เกิน 8 สไลด์ | ร่างโครง 8 สไลด์ไว้ล่วงหน้า วันที่ 30 พ.ย. แค่เพิ่มโจทย์ลับลงใน Solution Slide |
| **4. Backup Video** | ความยาวไม่เกิน 3 นาที | อัดวิดีโอจำลองการโทรเข้าจริงและหน้าจอ Agent เก็บไว้ตั้งแต่วันที่ 29 พ.ย. |
| **5. Live Demo** | สาธิตสดต่อหน้ากรรมการ | ซักซ้อมบทพูดและคิวโทรศัพท์ไว้ล่วงหน้า |
