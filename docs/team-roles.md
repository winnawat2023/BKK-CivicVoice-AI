# รายชื่อและบทบาททีมผู้เข้าแข่งขัน AI Skill Wars 2026 : AI For Bangkok
**ชื่อโปรเจกต์:** BKK CivicVoice AI (AI-First Omnichannel Contact Center for Bangkok)  
**ทีม / องค์กร:** ARK Insights Co., Ltd. (`ark-insights`)  
**โจทย์การแข่งขัน:** 02 Civic & Public Service Access (บริการภาครัฐและข้อมูลเมือง)  
**วันแข่งขันจริง:** วันจันทร์ที่ 30 พฤศจิกายน 2569 ณ BITEC Buri (ไบเทค บางนา)

---

## 1. ข้อมูลสมาชิกในทีม (Team Roster & Roles)

```
                       +---------------------------------------+
                       |        BKK CivicVoice AI Team         |
                       |       (ARK Insights - 4 สมาชิก)       |
                       +-------------------+-------------------+
                                           |
     +--------------------+----------------+--------------------+--------------------+
     |                    |                                     |                    |
     v                    v                                     v                    v
[ Member 1: Chaiyaporn ] [ Member 2: Watchara ]         [ Member 3: Peerapun ]  [ Member 4: Aitthiphon ]
Team Lead & Pitch Master  Genesys Cloud CX Engineer      AI Engine & Data Eng.   Frontend & Widget Eng.
```

### 👤 Member 1: Mr. Chaiyaporn Homtean
* **อีเมล:** `h.chaiyaporn@ark-insights.com`
* **บทบาทหลัก:** **Team Lead, Product & Pitch Master** (นำเสนอ & บริหารโปรเจกต์)
* **ความรับผิดชอบ:**
  * ควบคุมภาพรวมการพัฒนาตามแนวทาง **AI-DLC** และบริหารเวลาในวันแข่งขัน (ส่งงานก่อน 14:30 น.)
  * จัดทำเอกสารและ **Pitch Deck (สไลด์ไม่เกิน 8 หน้า)** ตามโครงสร้างเกณฑ์คะแนนของกรรมการ
  * กำกับ Demo Script และบันทึก **Backup Video (ความยาวไม่เกิน 3 นาที)**
  * เป็นตัวแทนหลักในการขึ้นนำเสนอ **Live Demo & Pitching** ต่อหน้าคณะกรรมการ (15:00 น.)

### 👤 Member 2: Mr. Watchara Bangkerdlap
* **อีเมล:** `b.watchara@ark-insights.com`
* **บทบาทหลัก:** **Genesys Cloud CX & Telephony Engineer** (สายโทรเข้า & การเชื่อมต่อ)
* **ความรับผิดชอบ:**
  * จัดการและคอนฟิกบน **Genesys Cloud CX Org (`ark-insights`)**
  * สร้าง Inbound Call Flow บน **Genesys Architect** (เบอร์ทดสอบรับสายโทรเข้าจริง)
  * คอนฟิก AudioHook / Webhook ส่ง Interaction ID, ANI (เบอร์ผู้โทร), และ Audio/Transcript มายัง Backend Middleware
  * ตั้งค่า Client Application Integration สำหรับฝัง Interaction Widget บนหน้าจอ Agent Desktop

### 👤 Member 3: Mr. Peerapun Sinyu
* **อีเมล:** `s.peerapun@ark-insights.com`
* **บทบาทหลัก:** **AI Engine & Data Engineer** (สมอง AI & เชื่อมโยง Data)
* **ความรับผิดชอบ:**
  * พัฒนา Core Backend Service ด้วย **FastAPI / Python**
  * เชื่อมต่อและปรับแต่ง Prompt ของโมเดล **Typhoon / Fine-tuned Gemma**
  * พัฒนาระบบ **Intent & Entity Extraction:** แปลงข้อความเสียงพูดภาษาไทยธรรมชาติให้เป็นโครงสร้าง JSON (หมวดหมู่: ถนน/ทางเท้า/ไฟฟ้า/ขยะ, พิกัดสถานที่, 50 เขต, ระดับความเร่งด่วน)
  * พัฒนาระบบ **Civic RAG Service** ดึงข้อมูลระเบียบขั้นตอน กทม. เพื่อตอบคำถามข้อมูลบริการราชการจบในสาย

### 👤 Member 4: Mr. Aitthiphon Puangsupan
* **อีเมล:** `p.aitthiphon@ark-insights.com`
* **บทบาทหลัก:** **Frontend Widget & Real-time Integration** (หน้าจอเจ้าหน้าที่ & Dashboard)
* **ความรับผิดชอบ:**
  * พัฒนาหน้าเว็บ **Genesys Interaction Widget (HTML/JS/Tailwind)** ที่ฝังใน Genesys Workspace
  * เชื่อมต่อ **WebSocket** เพื่อรับ-ส่งข้อมูล Live Transcription และกล่องสรุป 3 บรรทัด (AI Summary) แบบเรียลไทม์
  * พัฒนาปุ่มคำสั่ง Next Best Action เช่น "อนุมัติส่งเรื่องเข้าสำนักงานเขต (1-Click Ticket)"
  * สร้าง Simulator Script สำหรับทดสอบยิง Event เสมือนจริง เพื่อให้ระบบเสถียร 100% ในช่วง Demo

---

## 2. แผนการส่งงาน (Submission Deliverables Checklist - ส่งก่อน 14:30 น.)

- [ ] **1. Working Prototype:** รันได้จริงทั้งระบบโทรศัพท์ Genesys Cloud + AI Backend + Agent Widget (รับผิดชอบโดย Member 2, 3, 4)
- [ ] **2. GitHub Repository:** Public Repo หรือแชร์สิทธิ์ให้กรรมการ พร้อม README ละเอียด (รับผิดชอบโดย Member 1)
- [ ] **3. Pitch Deck (< 8 หน้า):** สไลด์นำเสนอ Problem, Solution, Architecture, AI Integration, Viability (รับผิดชอบโดย Member 1)
- [ ] **4. Backup Video (< 3 นาที):** วิดีโอบันทึกหน้าจอการทดสอบโทรเข้าจริงและแสดงผลบน Agent Widget เผื่อกรณีฉุกเฉิน (รับผิดชอบโดย Member 1, 4)
- [ ] **5. Live Demo:** ซักซ้อมคิวสาธิตสดต่อหน้าคณะกรรมการ (รับผิดชอบโดย สมาชิกทุกคน)
