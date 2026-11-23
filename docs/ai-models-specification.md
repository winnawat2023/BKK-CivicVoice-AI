# ข้อมูลจำเพาะทางเทคนิคด้าน AI (AI Models & Architecture Specification)
**โปรเจกต์:** BKK CivicVoice AI (AI-First Omnichannel Contact Center for Bangkok)  
**ทีม / องค์กร:** ARK Insights Co., Ltd. (`ark-insights`)  
**เป้าหมายการประมวลผล:** Real-time Voice Agent (< 1 วินาที End-to-End Latency)

---

## 1. โมเดล AI ที่ยืนยันใช้งานอย่างเป็นทางการ (Official Confirmed AI Stack)

จากการประเมินร่วมกันระหว่างความต้องการระบบ ความแม่นยำภาษาไทย และสเปกฮาร์ดแวร์บนเซิร์ฟเวอร์ (NVIDIA GB10 80GB VRAM / ARM aarch64) ได้ข้อสรุปอย่างเป็นทางการดังนี้:

### 🎙️ 1. Speech-to-Text (ASR Engine): `Faster-Whisper (large-v3-turbo)`
* **โมเดลที่เลือก:** `openai/whisper-large-v3-turbo` (รันผ่านเอนจิน `faster-whisper` / CTranslate2)
* **พอร์ตที่ให้บริการ:** `http://127.0.0.1:5001`
* **การใช้งาน VRAM:** ~3.5 – 4.0 GB
* **Latency:** ~100 – 200 ms (เร็วกว่า Whisper v3 ปกติ 8 เท่า)
* **เหตุผลที่เลือก:**
  * เหมาะสมที่สุดกับสัญญาณเสียงสายโทรศัพท์ (Telephony G.711 / 8kHz / 16kHz)
  * ทนทานต่อเสียงแทรก เสียงรถยนต์ และเสียงพูดเร็วของประชาชน
  * กิน VRAM น้อยมาก ทำให้เหลือพื้นที่ VRAM เกือบ 75GB ให้กับ LLM ได้อย่างสบาย

### 🧠 2. Large Language Model (Brain & Reasoning): `Typhoon-1.5X-8B-Instruct`
* **โมเดลที่เลือก:** `scb10x/typhoon-1.5x-8b-instruct` (พัฒนาโดย SCB 10X)
* **เอนจินที่ใช้เสิร์ฟ:** `vLLM` (OpenAI-compatible API Server)
* **พอร์ตที่ให้บริการ:** `http://127.0.0.1:8001/v1/chat/completions`
* **การใช้งาน VRAM:** ~12 – 14 GB (FP16 / BF16)
* **Generation Speed:** 60 – 90 tokens/วินาที บนชิป NVIDIA GB10
* **หน้าที่หลัก:**
  1. **Intent Classification:** คัดแยกระหว่าง "สอบถามข้อมูลบริการราชการ" กับ "แจ้งเรื่องร้องทุกข์ปัญหาเมือง"
  2. **Entity & Geo Extraction:** สกัดประเภทปัญหา (ถนน/ทางเท้า/ไฟฟ้า/ขยะ), พิกัดสถานที่, 50 สำนักงานเขต กทม., และระดับความเร่งด่วน
  3. **Executive Thai Summary:** สรุปสาระสำคัญ 3 บรรทัด สำหรับแสดงผลบนหน้าจอเจ้าหน้าที่ (Agent Widget)
  4. **Civic RAG Q&A:** ตอบคำถามระเบียบขั้นตอน กทม. อัตโนมัติจบในสาย
* **แผนการต่อยอด (Fine-tuning Plan):**
  * รองรับการ Fine-tune ด้วย LoRA / QLoRA โดยใช้ข้อมูลประวัติศาสตร์เรื่องร้องเรียนจริงของ กทม. กว่า 3,000,000 เรคคอร์ดในโฟลเดอร์ `opendata/`

---

## 2. แผนการจัดสรรพอร์ตบนเซิร์ฟเวอร์ DGX 101 (`192.168.200.101`)

```
[ Internet / Genesys Cloud CX ]
               │
               │ HTTPS / WSS (Port 443)
               ▼
[ Nginx Reverse Proxy & SSL (voiceai-demo.ark-insights.com) ]
               │
               ▼ (Internal Port 8000)
[ BKK CivicVoice AI Middleware (FastAPI Core Server) ]
       │                                     │
       │ (Port 5001)                         │ (Port 8001)
       ▼                                     ▼
[ Faster-Whisper ASR ]               [ vLLM : Typhoon-1.5X-8B ]
 (large-v3-turbo, ~4GB VRAM)          (Instruct, ~14GB VRAM)
```

| Service | Technology / Framework | Port | VRAM Usage |
| :--- | :--- | :---: | :---: |
| **Reverse Proxy** | Nginx + Let's Encrypt SSL | `80 / 443` | CPU |
| **Core Middleware** | FastAPI + WebSockets Hub | `8000` | CPU |
| **ASR Service** | Faster-Whisper (large-v3-turbo) | `5001` | ~4 GB |
| **LLM Inference** | vLLM + Typhoon-1.5X-8B-Instruct | `8001` | ~14 GB |
| **Total GPU Memory** | | | **~18 GB / 80+ GB** |
