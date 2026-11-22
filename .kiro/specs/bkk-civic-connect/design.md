# Technical Design Document
# BKK CivicConnect AI: Intelligent Omnichannel Citizen Contact Center for Bangkok
**Specification Path:** `.kiro/specs/bkk-civic-connect/design.md`  
**Referenced Data:** `opendata/processed/bkk_civic_analysis_summary.json` (3-Year BKK Civic Issues)

---

## 1. System Architecture Overview

```
                      +---------------------------------------+
                      |       Citizen Input Channels          |
                      |  1. Voice Call (PSTN / 1555 Hotline)  |
                      |  2. Digital Messaging (Web Chat)      |
                      +-------------------+-------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |     Genesys Cloud CX Platform         |
                      |          (Org: ark-insights)          |
                      |  - Architect Audio & Messaging Flows  |
                      |  - Webhook / WebSocket Outbound Event |
                      +-------------------+-------------------+
                                          |
                         (Voice Stream / Webhook Payload)
                                          |
                                          v
                      +---------------------------------------+
                      |  BKK CivicConnect Core Engine (FastAPI)|
                      +-------------------+-------------------+
                                          |
              +---------------------------+---------------------------+
              |                           |                           |
              v                           v                           v
   +--------------------+     +-----------------------+     +--------------------+
   | Speech-to-Text     |     | Thai LLM Engine       |     | BKK Open Data RAG  |
   | (Whisper / Thai STT|     | (Typhoon / Gemma)     |     | (3-Year Master DB  |
   | Real-time Stream)  |     | - Intent Classifier   |     |  885k+ Records)    |
   |                    |     | - Entity Extractor    |     | - SLA Benchmarks   |
   |                    |     | - Thai Summarization  |     | - Routing Rules    |
   +--------------------+     +-----------------------+     +--------------------+
              |                           |                           |
              +---------------------------+---------------------------+
                                          |
                                          v
                      +---------------------------------------+
                      |          Outputs & Actions            |
                      | 1. Auto Voice Response (TTS)          |
                      | 2. Auto Ticket Creation (API)         |
                      | 3. Genesys Agent Widget (Live Assist) |
                      +---------------------------------------+
```

---

## 2. Data Insights Driven Design (จากข้อมูลจริง 3 ปีย้อนหลัง)

จากการวิเคราะห์ข้อมูล Open Data กทม. กว่า 8.85 แสนรายการ:
1. **Top Problem Taxonomy:** จัดสรรโมเดลให้รองรับหมวดหมู่อัตโนมัติ:
   * `ถนน` (93,081 เคส) & `ทางเท้า` (82,392 เคส) -> ฝ่ายโยธา
   * `ผิดกฎจราจร` (80,594 เคส) -> ฝ่ายเทศกิจ / จราจร
   * `ไฟฟ้า` (69,848 เคส) -> ไฟฟ้าส่องสว่าง/การไฟฟ้านครหลวง
   * `ความสะอาด` (63,823 เคส) -> ฝ่ายรักษาความสะอาด
2. **Hotspot District Routing:** มีระบบคัดแยกปลายทางส่งต่ออัตโนมัติไปยังสำนักงานเขตเป้าหมายสูง (จตุจักร, วัฒนา, บางกะปิ, คลองเตย, ปทุมวัน)
3. **SLA Predictor:** มีโมเดลคำนวณระยะเวลาคาดการณ์ในการแก้ไขปัญหา แจ้งประชาชนในสายทันที

---

## 3. Component Specifications

### 3.1 Genesys Cloud Webhook Integration (`/api/v1/genesys/webhook`)
* **Method:** `POST`
* **Input Schema:**
```json
{
  "interaction_id": "string",
  "ani": "string (caller phone number)",
  "channel": "voice | chat",
  "text_or_audio_stream": "string",
  "timestamp": "ISO8601"
}
```

### 3.2 AI Intent & Entity Extraction (`/api/v1/civic/classify`)
* **Prompt Engine:** Typhoon / Fine-tuned Gemma
* **Output Schema:**
```json
{
  "intent": "complaint | inquiry",
  "category": "ถนน | ทางเท้า | ผิดกฎจราจร | ไฟฟ้า | ความสะอาด | อื่นๆ",
  "district": "string (1 ใน 50 เขต กทม.)",
  "location_detail": "string",
  "urgency": "low | medium | high",
  "summary_th": "สรุปสั้น 1-2 ประโยคภาษาไทย",
  "suggested_action": "หน่วยงานที่ต้องประสานงาน"
}
```

### 3.3 Genesys Agent Interaction Widget (Frontend HTML/JS)
* **Embedded URL:** `https://host/widget/index.html`
* **Features:**
  * Real-time WebSocket connection to backend
  * Live Transcription Display
  * Real-time 3-bullet AI Summary
  * One-click "Create Ticket" & "Forward to District Office"
