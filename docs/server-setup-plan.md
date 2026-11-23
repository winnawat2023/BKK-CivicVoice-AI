# แผนการติดตั้งและเตรียมความพร้อมเซิร์ฟเวอร์ DGX (100 & 101)
**โดเมนเป้าหมาย:** `voiceai-demo.ark-insights.com` (Port 443 HTTPS)  
**ทีม / องค์กร:** ARK Insights Co., Ltd.

---

## 1. ผลการวินิจฉัยเครือข่ายเบื้องต้น (Network Diagnostics)

จากการทดสอบจากเครื่อง Mac เครื่องนี้ไปยัง IP `192.168.200.100` และ `192.168.200.101`:
* **สถานะ:** เครื่อง Mac อยู่คนละวงเครือข่าย (`192.168.5.x`) และยังไม่สามารถข้าม Routing ไปยังวง Server (`192.168.200.x`) ได้โดยตรงจาก terminal เครื่องนี้ (Operation timed out)
* **วิธีแก้:** ต้อง SSH เข้าเครื่อง DGX โดยตรงจากเครื่องที่มีสิทธิ์เข้าถึงวง `192.168.200.x` (หรือผ่าน Jump Host / VPN ของออฟฟิศ)

---

## 2. ขั้นตอนการตรวจสอบและแก้ไขบนเครื่อง DGX 101 (`192.168.200.101`)

### 🔹 Step 1: SSH เข้าเครื่อง DGX 101
```bash
ssh gwplus@192.168.200.101
# ใส่รหัสผ่าน: P@ssw0rd
```

### 🔹 Step 2: รันสคริปต์ตรวจเช็คสภาพเครื่อง (Diagnostic)
สามารถคัดลอกคำสั่งนี้ไปรันบน Terminal ของ DGX 101 เพื่อตรวจดูว่ามีอะไรพร้อมแล้วบ้าง:
```bash
curl -sL https://raw.githubusercontent.com/winnawat2023/BKK-CivicVoice-AI/main/scripts/check_dgx101.sh | bash
```
* ตรวจสอบว่า Driver การ์ดจอ NVIDIA ปกติไหม
* ตรวจสอบว่า Nginx หรือ Service อื่นจองพอร์ต 80 / 443 อยู่หรือไม่

### 🔹 Step 3: รันสคริปต์ติดตั้งระบบทั้งหมดแบบอัตโนมัติ (1-Command Setup)
รันคำสั่งเดียวนี้บนเครื่อง DGX 101 เพื่อ Clone โค้ด, ติดตั้ง FastAPI Service และตั้งค่า Nginx + SSL ทันที:
```bash
curl -sL https://raw.githubusercontent.com/winnawat2023/BKK-CivicVoice-AI/main/scripts/setup_dgx101.sh | bash
```

---

## 3. ขั้นตอนการเตรียมเครื่อง DGX 100 (`192.168.200.100`) สำหรับ AI Inference

### 🔹 Step 1: SSH เข้าเครื่อง DGX 100
```bash
ssh appadm@192.168.200.100
# ใส่รหัสผ่าน: Ark@2018
```

### 🔹 Step 2: รันโมเดลภาษาไทย (Typhoon / Gemma) ด้วย vLLM หรือ Ollama
รัน Service ให้บริการ LLM API บนพอร์ต `8001` (ให้เครื่อง 101 เรียกเข้ามา):
```bash
# ตัวอย่างการรัน vLLM เสิร์ฟโมเดล Typhoon หรือ Gemma:
python3 -m vllm.entrypoints.openai.api_server \
    --model scb10x/typhoon-1.5x-7b-instruct \
    --port 8001 \
    --host 0.0.0.0 \
    --tensor-parallel-size 1
```

---

## 4. ผลลัพธ์ที่ได้เมื่อเสร็จสิ้น
1. **Genesys Webhook:** `https://voiceai-demo.ark-insights.com/api/v1/genesys/webhook` พร้อมรับสายโทรเข้าจริง
2. **Agent Widget:** `https://voiceai-demo.ark-insights.com/widget/index.html` พร้อมฝังบน Genesys Workspace
3. **ความเร็ว:** ประมวลผลคำตอบภาษาไทยผ่าน GPU บน DGX 100 ภายในเวลา < 0.5 วินาที!
