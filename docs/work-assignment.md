# ใบสั่งงานและแผนปฏิบัติการรายบุคคล (Work Assignment & Action Plan)
**โปรเจกต์:** BKK CivicVoice AI (AI-First Omnichannel Contact Center for Bangkok)  
**ทีม / องค์กร:** ARK Insights Co., Ltd. (`ark-insights`)  
**เป้าหมาย:** พัฒนาระบบให้เสร็จสมบูรณ์ 100% พร้อมทดสอบ End-to-End ภายใน **วันศุกร์ที่ 28 พ.ย. 2569**  
**วันแข่งขันจริง:** วันจันทร์ที่ 30 พฤศจิกายน 2569 ณ BITEC Buri

---

## 👤 Member 1: Mr. Chaiyaporn Homtean (Team Lead & Pitch Master)
* **อีเมล:** `h.chaiyaporn@ark-insights.com`
* **บทบาท:** นำเสนอ, บริหารโปรเจกต์, และกำกับเวลาส่งมอบ

### รายการงานที่ต้องส่งมอบ (Deliverables):
1. **Pitch Deck (สไลด์ไม่เกิน 8 หน้า):** จัดทำโครงสร้างสไลด์ตามเกณฑ์การตัดสิน (เสร็จภายใน 27 พ.ย.)
   * Slide 1: Cover (BKK CivicVoice AI)
   * Slide 2: Problem & Evidence (อ้างอิงสถิติ Open Data กทม. 3 ล้านเคส จาก `opendata/processed/`)
   * Slide 3: The Gap (ทำไม 1555 สายแน่น และคนสูงอายุ/คนขับรถไม่ใช้แอปปักหมุด)
   * Slide 4: Solution Architecture (Genesys Cloud CX + Typhoon/Gemma AI + 50 เขต)
   * Slide 5: AI Integration Depth (Logic การสกัด Entity และ RAG ตอบระเบียบราชการ)
   * Slide 6: Demo Scenarios (สายโทรจริง + หน้าจอ Agent Desktop)
   * Slide 7: Business & Social Impact (ลดเวลารอสาย 70%, ลด AHT 50%)
   * Slide 8: Team ARK Insights & Roadmap
2. **Demo Script & Backup Video (ความยาว < 3 นาที):**
   * เขียนบทสนทนาจำลองสำหรับโทรเข้าช่วง Live Demo
   * อัดคลิปวิดีโอหน้าจอสำรองเผื่อกรณีอินเทอร์เน็ตหน้างานมีปัญหา (เสร็จภายใน 29 พ.ย.)
3. **คุมเวลาการแข่งขัน (30 พ.ย.):**
   * รับโจทย์ลับช่วงเช้า (09:45 น.) และประสานทีมปรับฟีเจอร์
   * ตรวจสอบความเรียบร้อยของ GitHub Repo และกดส่งงานก่อน 14:30 น.

---

## 👤 Member 2: Mr. Watchara Bangkerdlap (Genesys Cloud CX & Telephony Engineer)
* **อีเมล:** `b.watchara@ark-insights.com`
* **บทบาท:** ระบบโทรศัพท์, Inbound Routing, และการเชื่อมต่อ Genesys Cloud CX

### รายการงานที่ต้องส่งมอบ (Deliverables):
1. **Inbound Call Flow บน Genesys Architect (เสร็จภายใน 25 พ.ย.):**
   * สร้าง Call Flow บน Genesys Cloud Org `ark-insights`
   * ผูกเบอร์โทรทดสอบ (DID / WebRTC) ที่กรรมการและทีมงานสามารถใช้โทรศัพท์มือถือโทรเข้าได้จริง
2. **Data Action / Webhook Integration (เสร็จภายใน 26 พ.ย.):**
   * ตั้งค่าส่ง Interaction Payload (ANI เบอร์ผู้โทร, Interaction ID) มายัง Backend Middleware (`/api/v1/genesys/webhook`)
   * ตั้งค่าโอนสายมายังคิวเจ้าหน้าที่มนุษย์ (Agent Queue) กรณีที่ประชาชนต้องการคุยกับเจ้าหน้าที่
3. **Client Application Integration (เสร็จภายใน 27 พ.ย.):**
   * ฝัง Interaction Widget URL (`src/frontend/widget/index.html`) บน Genesys Agent Desktop Workspace

---

## 👤 Member 3: Mr. Peerapun Sinyu (AI Engine & Data Engineer)
* **อีเมล:** `s.peerapun@ark-insights.com`
* **บทบาท:** Core API Backend, Typhoon/Gemma Thai LLM, และ Civic RAG

### รายการงานที่ต้องส่งมอบ (Deliverables):
1. **Core FastAPI Backend (`src/backend/main.py`) (เสร็จภายใน 24 พ.ย.):**
   * ตั้งค่ารัน Server และ Endpoint รับ Webhook จาก Genesys Cloud
   * จัดการระบบ In-memory Database / SQLite สำหรับเก็บประวัติ Ticket
2. **Thai LLM Reasoning Engine (Typhoon / Fine-tuned Gemma) (เสร็จภายใน 25 พ.ย.):**
   * ออกแบบ Prompt สกัด Structured JSON (Intent, Category 5 หมวดหลัก, เขต 50 เขต, ระดับความเร่งด่วน)
   * ทดสอบกับชุดข้อมูลจริงจาก `opendata/processed/` ให้มีความแม่นยำสูง
3. **Civic RAG Service (เสร็จภายใน 26 พ.ย.):**
   * เชื่อมต่อคลังข้อมูลระเบียบราชการ กทม. (การทำบัตรประชาชน, ทะเบียนบ้าน, เบี้ยผู้สูงอายุ) เพื่อให้ AI ตอบประชาชนจบในสายได้ทันที
4. **WebSocket Push Engine (เสร็จภายใน 27 พ.ย.):**
   * ระบบ Push Live Transcript และ AI Summary 3 บรรทัด ส่งตรงไปยังหน้าจอ Widget ของ Member 4

---

## 👤 Member 4: Mr. Aitthiphon Puangsupan (Frontend Widget & Real-time Integration)
* **อีเมล:** `p.aitthiphon@ark-insights.com`
* **บทบาท:** หน้าจอ Genesys Agent Interaction Widget และ Test Simulator

### รายการงานที่ต้องส่งมอบ (Deliverables):
1. **Genesys Agent Interaction Widget (`src/frontend/widget/index.html`) (เสร็จภายใน 25 พ.ย.):**
   * พัฒนาหน้าจอ Responsive UI ด้วย Tailwind CSS เหมาะสำหรับขนาดกรอบ iframe ใน Genesys Workspace
   * กล่องแสดงผล Live Thai Transcript (ถอดเสียงภาษาไทยสด)
   * กล่องแสดงผล AI Executive Summary (สรุป 3 บรรทัด + สำนักงานเขตเป้าหมาย + SLA คาดการณ์)
2. **WebSocket Client Integration (เสร็จภายใน 26 พ.ย.):**
   * เชื่อมต่อ WebSocket กับ Backend ของ Member 3 รับข้อมูลแบบเรียลไทม์
   * ปุ่มกด "1-Click Dispatch: อนุมัติส่งเรื่องเข้าสำนักงานเขต"
3. **End-to-End Simulation Script (`src/tests/simulate_call.py`) (เสร็จภายใน 27 พ.ย.):**
   * สร้างสคริปต์ยิงทดสอบจำลองสายโทรเข้าพร้อมข้อความเสียงภาษาไทย เพื่อใช้ซ้อม Demo ซ้ำๆ จนมั่นใจว่าระบบไม่มีทางล่ม

---

## 🎯 กำหนดการนัดหมายทดสอบระบบร่วมกัน (Integration Milestone)

* **วันศุกร์ที่ 28 พ.ย. 2569 เวลา 14:00 น.:** นัดทดสอบระบบ **End-to-End Full Integration Test** ร่วมกันทั้ง 4 คน
  * ทดลองใช้โทรศัพท์จริงโทรเข้าเบอร์ Genesys Cloud
  * ตรวจสอบว่าบอทรับสายและเสียงตอบกลับทำงานได้
  * ตรวจสอบว่าหน้าจอ Agent Widget บนเครื่องเจ้าหน้าที่แสดง Live Transcript และสรุปผลได้ภายใน 2 วินาที
