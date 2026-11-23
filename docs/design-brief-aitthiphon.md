# 📋 UI/UX Design Brief: BKK CivicVoice AI
**โครงการ:** AI Skill Wars 2026 : AI For Bangkok  
**ผู้รับผิดชอบหลัก:** คุณอิทธิพล พวงสุพรรณ (Frontend Widget & Integration Specialist)  
**ผู้ออกบรีฟ:** คุณชัยพร หอมเทียน (Team Lead)  
**วันส่งมอบแบบ / Prototype:** 27 พฤศจิกายน 2569 (เพื่อซักซ้อมก่อนแข่งจริง 30 พ.ย.)

---

## 1. บริบทและโจทย์หลัก (Context & Objectives)
เรากำลังสร้างระบบ **AI-First Omnichannel Contact Center** เพื่อยกระดับสายด่วน 1555 ของกรุงเทพมหานคร เชื่อมต่อกับ **Genesys Cloud CX (Org: `ark-insights`)** 

หน้าจอที่คุณอิทธิพลต้องออกแบบและพัฒนา มี **2 ส่วนหลัก**:
1. **Agent Copilot Widget (Iframe ใน Genesys Cloud):** สำหรับเจ้าหน้าที่รับสาย 1555 ช่วยถอดเสียงสด สรุปประเด็น แนะนำเขตรับผิดชอบ และกดส่งเรื่องใน 1 คลิก
2. **Citizen Tracking & Public Dashboard (Web Responsive):** สำหรับประชาชนตรวจเช็กสถานะคำร้องผ่าน SMS Link หรือบนเว็บ

---

## 2. หน้าจอที่ 1: Genesys Agent Copilot Widget (สำคัญอันดับ 1 🌟)

### 📌 ตำแหน่งและการแสดงผล
- เป็น **Embedded Iframe Client Application** ฝังอยู่ในหน้าจอ Agent Desktop ของ Genesys Cloud CX (ขนาดพื้นที่ทำงานประมาณ **400px - 500px** ในแถบด้านข้าง หรือเต็มจอกรณีเปิดแท็บแยก)
- ต้องการดีไซน์แบบ **Clean, Modern, High Contrast, Compact UI** ให้อ่านง่าย รวดเร็ว สบายตาระหว่างเจ้าหน้าที่สนทนาสาย

### องค์ประกอบบนหน้าจอ (Components & Wireframe Flow):
1. **Header & Status Bar:**
   - โลโก้ BKK CivicVoice AI + Badge องค์กร (`ark-insights`)
   - ไฟสถานะ Call & AI Sync (เช่น 🟢 *Live Syncing - Faster-Whisper + Typhoon 8B*)
   - ข้อมูลสาย: `Interaction ID` และ `เบอร์โทรประชาชน (ANI)`
2. **Live Thai Transcript (ASR Stream):**
   - กล่องแสดงผลข้อความถอดเสียงภาษาไทยแบบ Real-time จาก Faster-Whisper
   - แยกสีฟองคำพูดชัดเจนระหว่าง **[เจ้าหน้าที่ 1555]** และ **[ประชาชน]**
   - มีไฮไลท์คำสำคัญอัตโนมัติ (Named Entity Recognition: NER) เช่น **ชื่อเขต, ถนน, ซอย, จุดสังเกต**
3. **AI Copilot Insight & Auto-Classification (LLM Typhoon Engine):**
   - **สรุปสาระสำคัญ (Executive Summary):** สรุปประเด็น 2–3 บรรทัด เช่น *"แจ้งฝาท่อระบายน้ำชำรุด ฝาท่อเปิดทิ้งไว้ เสี่ยงอุบัติเหตุรถจักรยานยนต์"*
   - **หมวดหมู่ปัญหา (Category):** เช่น ถนน/ทางเท้า, ท่อระบายน้ำ, ขยะตกค้าง, แสงสว่าง (อิงจาก 21 หมวด Traffy Fondue)
   - **พิกัด & เขตเป้าหมาย (Auto District):** ระบุเขตอัตโนมัติ (เช่น *เขตคลองเตย*) พร้อมค่าความแม่นยำ AI Confidence (เช่น 96%)
   - **ระดับความเร่งด่วน (Urgency):** Badge สีเตือนชัดเจน `CRITICAL` (แดง) / `HIGH` (ส้ม) / `NORMAL` (เขียว)
   - **SLA คาดการณ์:** วิเคราะห์จากฐานข้อมูลสถิติ 3 ล้านเคส เช่น *คาดการณ์เสร็จสิ้นใน 3 วัน*
4. **Interactive Action Zone (1-Click Operations):**
   - **ปุ่ม Action เด่นที่สุด:** `[ 1-Click บันทึกคำร้อง & ส่งสำนักงานเขต ]` (สร้าง Ticket และยิง API ส่งฝ่ายโยธา/เทศกิจทันที)
   - **ปุ่ม SMS ส่งพิกัด:** `[ ส่ง SMS ปชช. ขอปักหมุด GPS/รูปถ่าย ]` (แก้ Pain Point คลาสสิกของ 1555 ที่บอกตำแหน่งไม่ถูก)
   - **ปุ่มตรวจสอบเคสซ้ำ (Duplicate Check):** แจ้งเตือนหากมีประชาชนแจ้งจุดเดียวกันใน 24 ชม. ที่ผ่านมา (เช่น *"พบปัญหาคล้ายกันในระยะ 100 เมตร 2 เคส"*)

---

## 3. หน้าจอที่ 2: Citizen Tracking & Executive Dashboard (หน้าเสริมสำหรับการ Demo)

### 3.1 Citizen Mobile Tracking View (Mobile-First Web):
- หน้าเว็บที่เปิดขึ้นเมื่อประชาชนกดลิงก์จาก SMS:
  - การ์ดแสดงสถานะคำร้องแบบ Timeline: `รับเรื่องแล้ว` ➔ `ส่งเขตคลองเตย` ➔ `กำลังดำเนินการ` ➔ `เสร็จสิ้น`
  - สรุปปัญหาที่แจ้ง + วันเวลา + เลขที่คำร้อง (Ticket ID)
  - ช่องให้อัปโหลดรูปเพิ่มเติม หรือกดแชร์ GPS ปัจจุบันเพื่อความแม่นยำ

### 3.2 Executive Monitor Dashboard (สำหรับโชว์ใน Pitch Deck / สไลด์):
- แดชบอร์ดมอนิเตอร์ภาพรวม กทม. 50 เขต:
  - กราฟิก Heatmap ปัญหาในกรุงเทพฯ
  - ตัวเลข KPI: สถิติรับสายต่อวัน, อัตรา First Contact Resolution (FCR), เวลาเฉลี่ยต่อสาย (AHT ลดลงจาก 4.5 นาที เหลือ 2.5 นาที)

---

## 4. Design Guidelines & Tech Stack

| ด้าน | รายละเอียดข้อกำหนด |
|---|---|
| **Tech Framework** | **HTML5 + Tailwind CSS + Vanilla JS** (หรือ React/Vite) เน้น Bundle เล็ก โหลดเร็วมาก ไม่หน่วงระบบ Genesys |
| **Fonts** | Google Fonts: `Sarabun` (ภาษาไทยทางการและชัดเจน) หรือ `Prompt` |
| **Color Palette** | • **Primary:** Navy / Slate (`#0F172A`, `#1E293B`) ให้ความรู้สึกมั่นคง น่าเชื่อถือ<br>• **Brand Accent:** Emerald Green (`#10B981`) สื่อถึงกรุงเทพฯ เมืองสีเขียว / Smart City<br>• **AI Highlight:** Electric Blue / Cyan (`#06B6D4`, `#3B82F6`) แสดงถึงความล้ำสมัยของ AI Copilot |
| **Responsiveness** | Width ยืดหยุ่นได้ดีระหว่าง 380px ถึง 100% |
| **Data Connection** | รองรับ **WebSocket** จาก `FastAPI` (`ws://localhost:8000/ws/agent/{interaction_id}`) มีไฟล์ Mockup Data ให้พร้อมทดสอบแล้วที่ `src/tests/simulate_call.py` |

---

## 5. สิ่งที่มีพร้อมให้คุณอิทธิพลเริ่มงานได้ทันที
1. **โค้ด Widget ตั้งต้น (HTML/Tailwind):** อยู่ในโฟลเดอร์ [`src/frontend/widget/index.html`](file:///Users/h.chaiyaporn/code/AI-DLC/src/frontend/widget/index.html)
2. **Backend API & WebSocket Server:** รันอยู่ที่ `src/backend/main.py` (รันพอร์ต 8000 มีทั้ง REST API และ WebSocket)
3. **สคริปต์ยิง Mock Data สด:** สามารถรัน `python src/tests/simulate_call.py` เพื่อจำลองเสียงสนทนาและดู Event วิ่งเข้าหน้าจอแบบ Real-time ได้ทันที

---
*จัดทำขึ้นเพื่อเตรียมความพร้อมสู่ชัยชนะในงาน AI Skill Wars 2026 : AI For Bangkok*
