# BKK CivicVoice AI: คู่มือ ASR Service (Faster-Whisper)

เอกสารนี้สำหรับทีมที่ต้องติดตั้ง รัน หรือเชื่อมต่อบริการถอดเสียง (Speech-to-Text) ได้แก่ AI Engine (Peerapun), Genesys Cloud CX (Watchara), Agent Widget (Aitthiphon) และทีม Demo

โค้ดอยู่ที่ `src/asr/` เป็นบริการแยกจาก Middleware (`src/backend/`) รันที่พอร์ต `5001` ตามผังใน [ai-models-specification.md](ai-models-specification.md) บริการนี้ **ไม่แตะ Widget** Widget ได้ข้อความถอดเสียงจาก Middleware ผ่าน WebSocket เดิม (`transcript` event) เหมือนเดิมทุกประการ

---

## 1. ภาพรวม

```
เสียงสาย (PCM16 / G.711 µ-law)         ไฟล์เสียง (wav, mp3, ...)
          │ WebSocket                          │ HTTP POST
          ▼                                    ▼
   /v1/stream/{interaction_id}            /v1/transcribe
          └────────────────┬───────────────────┘
                           ▼
              ASR Service (FastAPI, พอร์ต 5001)
              Faster-Whisper large-v3-turbo
                           │  POST /api/v1/calls/{interaction_id}/segments
                           ▼
              CivicVoice API (พอร์ต 8000)  ──WebSocket──►  Agent Widget
              วิเคราะห์ intent / ออก Ticket        (transcript, summary)
```

- **ASR Service** แปลงเสียงเป็นข้อความ แล้วส่งต่อไปที่ `POST /api/v1/calls/{id}/segments` ของ Middleware ซึ่งมีอยู่แล้ว (ดู [api-guide.md](api-guide.md) หัวข้อ 5.3) Middleware ไม่ต้องแก้ไขอะไร
- ข้อความ `partial` (is_final = false) ทำให้ Widget เห็นคำบรรยายสด ข้อความ `final` ทำให้ Middleware วิเคราะห์สดและส่งสรุป 3 บรรทัดให้ Widget
- บริการนี้ **ไม่เก็บไฟล์เสียงและไม่บันทึกข้อความถอดเสียงลง log** (log มีเฉพาะความยาวและภาษา) ไม่มีฐานข้อมูล

---

## 2. การติดตั้งและรัน

ต้องใช้ Python 3.10 ขึ้นไป (ทดสอบกับ 3.12) ครั้งแรกที่รัน ระบบจะดาวน์โหลดโมเดลจาก Hugging Face (`large-v3-turbo` ประมาณ 1.6 GB) จึงต้องต่ออินเทอร์เน็ตครั้งแรก

**Windows (PowerShell)**

```powershell
cd src\asr
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env        # ปรับค่าได้ตามหัวข้อ 3
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 5001
```

**Linux / DGX 101**

```bash
cd src/asr
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 5001
```

ตรวจว่ารันแล้ว: `GET http://127.0.0.1:5001/health?check_backend=true` ควรได้ `"status": "ok"` และ `backend.reachable: true` (เมื่อ Middleware รันอยู่) Swagger อยู่ที่ `/docs`

**เครื่องพัฒนาที่ไม่มี GPU:** ตั้ง `ASR_MODEL=small` (หรือ `base`) ใน `.env` เพื่อโหลดและตอบเร็วขึ้น คุณภาพภาษาไทยจะลดลงมาก ใช้ทดสอบ flow เท่านั้น ห้ามใช้ตัดสินความแม่นยำ

> **ข้อควรระวังเรื่องเวอร์ชัน:** `requirements.txt` กำหนด `av>=11,<19` โดยตั้งใจ `faster-whisper` 1.2.x เรียก `av.open(metadata_errors=...)` ซึ่ง PyAV 19 ตัดออกแล้ว ถ้าติดตั้ง PyAV 19 การอัปโหลดไฟล์ทุกไฟล์จะได้ HTTP 500 (`unexpected keyword argument 'metadata_errors'`) ชุดเทส `tests/test_decode_dependencies.py` ตรวจจุดนี้โดยเฉพาะ

---

## 3. ตัวแปรสภาพแวดล้อม

อ่านจาก environment หรือไฟล์ `src/asr/.env` (ดูตัวอย่างและคำอธิบายครบใน `src/asr/.env.example`) ไม่มี credential ในบริการนี้

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `ASR_MODEL` | `large-v3-turbo` | ชื่อโมเดล, Hugging Face repo id หรือโฟลเดอร์โมเดล CTranslate2 ในเครื่อง |
| `ASR_DEVICE` | `auto` | `auto` ใช้ `cuda` เมื่อเห็น GPU ไม่เช่นนั้น `cpu` |
| `ASR_COMPUTE_TYPE` | `auto` | `auto` เลือกชนิดที่ CTranslate2 บน GPU รองรับ (`float16` ถ้ารองรับ เช่น GPU รุ่นใหม่ ไม่เช่นนั้น `int8_float32` เช่น GTX 1050) และ `int8` บน CPU |
| `ASR_PRELOAD` | `false` | `true` โหลดโมเดลตอนเริ่มบริการ (สายแรกจะไม่ช้า) แนะนำ `true` บนเซิร์ฟเวอร์ |
| `ASR_DOWNLOAD_ROOT` | ว่าง | โฟลเดอร์เก็บโมเดล (ว่าง = cache ของ Hugging Face) |
| `ASR_LANGUAGE` | `auto` | `th`, `en` หรือ `auto` |
| `ASR_ALLOWED_LANGUAGES` | `th,en` | ภาษาที่รับเมื่อ `auto` |
| `ASR_FALLBACK_LANGUAGE` | `th` | ถ้า `auto` ตรวจเจอภาษานอกรายการด้านบน ระบบถอดซ้ำเป็นภาษานี้ (Whisper มักเดาภาษาผิดกับเสียงโทรศัพท์สั้น ๆ) |
| `ASR_INITIAL_PROMPT` | คำศัพท์ กทม. | คำใบ้การสะกด (ท่อระบายน้ำ, สำนักงานเขต ฯลฯ) ใช้ **เฉพาะตอนถอดเป็นภาษาไทย** ตั้งว่างเพื่อปิด (ดูหมายเหตุหัวข้อ 7) |
| `ASR_VAD_FILTER` | `true` | ตัดช่วงเงียบก่อนถอดเสียง ลดข้อความหลอน |
| `ASR_MAX_CONCURRENCY` | `1` | จำนวนการถอดเสียงพร้อมกันต่อ process |
| `ASR_MAX_UPLOAD_MB` | `25` | ขนาดไฟล์สูงสุดของ `/v1/transcribe` (เกินจะได้ 413) |
| `ASR_ENERGY_THRESHOLD` | `0.012` | ความดัง (RMS 0 ถึง 1) ที่นับเป็นเสียงพูดในโหมด stream ถ้าสายมีเสียงรบกวนมากให้เพิ่มค่านี้ |
| `ASR_ENDPOINT_SILENCE_MS` | `700` | เงียบนานเท่านี้ถือว่าผู้โทรพูดจบประโยค (ออก `final`) |
| `ASR_PARTIAL_INTERVAL_MS` | `1500` | ส่ง `partial` ทุกกี่ ms ระหว่างที่ผู้โทรพูด |
| `ASR_MIN_SPEECH_MS` | `250` | เสียงสั้นกว่านี้ถือเป็นเสียงรบกวน |
| `ASR_MAX_UTTERANCE_S` | `20` | พูดต่อเนื่องเกินนี้จะบังคับออก `final` |
| `BACKEND_URL` | `http://127.0.0.1:8000` | ที่อยู่ CivicVoice API |
| `BACKEND_TIMEOUT_S` | `5` | timeout เมื่อส่งต่อ |
| `FORWARD_DEFAULT` | `true` | ส่งต่อไป Middleware อัตโนมัติเมื่อมี `interaction_id` |
| `ASR_PORT` | `5001` | พอร์ตเมื่อรันด้วย `python main.py` |
| `CORS_ORIGINS` | `*` | ควรจำกัดใน production |

---

## 4. API

ไม่มีการยืนยันตัวตน (เหมือน Middleware) ให้เปิดเฉพาะในเครือข่ายภายใน ห้ามเปิดพอร์ต 5001 สู่อินเทอร์เน็ต

### 4.1 `GET /health`

| Query | ค่าเริ่มต้น | คำอธิบาย |
|---|---|---|
| `check_backend` | `false` | `true` จะตรวจ CivicVoice API ด้วย ผลอยู่ในฟิลด์ `backend` |

```json
{
  "status": "ok",
  "version": "1.0.0",
  "model": "large-v3-turbo",
  "model_loaded": true,
  "device": "cuda",
  "compute_type": "float16",
  "language": "auto",
  "allowed_languages": ["th", "en"],
  "backend_url": "http://127.0.0.1:8000"
}
```

`device` และ `compute_type` จะเป็นค่าจริงหลังโหลดโมเดลแล้ว ใช้ตรวจว่าบนเซิร์ฟเวอร์ใช้ GPU จริงหรือตกมาใช้ CPU

### 4.2 `POST /v1/transcribe` (อัปโหลดไฟล์เสียง)

`multipart/form-data` รองรับ wav, mp3, m4a, ogg, flac, webm และชนิดอื่นที่ ffmpeg/PyAV อ่านได้ ตัวถอดรหัสแปลงเป็น 16 kHz mono ให้เอง

| ฟิลด์ | จำเป็น | ค่าเริ่มต้น | คำอธิบาย |
|---|---|---|---|
| `file` | ✅ | | ไฟล์เสียง |
| `language` | | ตาม `ASR_LANGUAGE` | `th`, `en` หรือ `auto` |
| `interaction_id` | | | Genesys Conversation ID ถ้าใส่ จะส่งข้อความต่อไป Middleware |
| `speaker` | | `caller` | `caller`, `bot` หรือ `agent` |
| `ani` | | | เบอร์ผู้โทร (ส่งต่อไป Middleware เท่านั้น บริการนี้ไม่เก็บ) |
| `is_final` | | `true` | ค่า `is_final` ที่ส่งต่อ |
| `forward` | | ตาม `FORWARD_DEFAULT` | `false` เพื่อถอดเสียงอย่างเดียว ไม่ส่งต่อ |

```bash
curl -X POST http://127.0.0.1:5001/v1/transcribe \
  -F "file=@call.wav" -F "language=th" -F "interaction_id=CALL-9042-DEMO"
```

Response

```json
{
  "text": "แถวซอยสุขุมวิท 50 มีท่อระบายน้ำแตก ...",
  "language": "th",
  "language_probability": 1.0,
  "duration": 6.9,
  "segments": [{ "start": 0.0, "end": 6.9, "text": "แถวซอยสุขุมวิท 50 มีท่อระบายน้ำแตก ..." }],
  "interaction_id": "CALL-9042-DEMO",
  "forwarded": { "attempted": true, "ok": true, "status": 200, "error": null }
}
```

- `forwarded.attempted` เป็น `false` เมื่อไม่มี `interaction_id`, ปิด `forward` หรือไม่พบเสียงพูด (`text` ว่าง)
- ถ้า Middleware ล่มหรือปฏิเสธ การถอดเสียงยังสำเร็จ (HTTP 200) และ `forwarded.ok` เป็น `false` พร้อม `error` หรือ `status`

| HTTP | สาเหตุ |
|---|---|
| 400 | ไฟล์ว่าง |
| 413 | ไฟล์ใหญ่เกิน `ASR_MAX_UPLOAD_MB` |
| 422 | ไม่ใช่ไฟล์เสียง (ถอดรหัสไม่ได้) หรือค่าฟอร์มผิด (เช่น `speaker` ไม่อยู่ในรายการ) |
| 500 | การถอดเสียงล้มเหลวภายใน (เช่น หน่วยความจำ GPU ไม่พอ) |
| 503 | โหลดโมเดลไม่ได้ (ดาวน์โหลดไม่สำเร็จ, path ผิด) |

### 4.3 `WS /v1/stream/{interaction_id}` (เสียงสด)

ผู้เรียก (Media Gateway / ตัวเชื่อม Genesys) ส่งเสียงดิบเป็น binary frame ต่อเนื่อง บริการตัดเป็นประโยคเองและส่งผลกลับ

**Query parameter**

| ชื่อ | ค่าเริ่มต้น | คำอธิบาย |
|---|---|---|
| `encoding` | `pcm16` | `pcm16` (signed 16-bit little-endian, mono) หรือ `mulaw` (G.711 µ-law, mono) |
| `sample_rate` | `16000` | 8000 ถึง 48000 สายโทรศัพท์ G.711 ใช้ `encoding=mulaw&sample_rate=8000` |
| `language` | ตาม `ASR_LANGUAGE` | `th`, `en` หรือ `auto` |
| `speaker` | `caller` | `caller`, `bot` หรือ `agent` |
| `ani` | | เบอร์ผู้โทร (ส่งต่อไป Middleware) |
| `forward` | ตาม `FORWARD_DEFAULT` | `false` = ส่ง event กลับผู้เรียกอย่างเดียว |

พารามิเตอร์ผิด (`encoding` หรือ `sample_rate`) จะได้ event `error` แล้วปิดด้วย code 1008

**Server → client events** (JSON ทุกเฟรมมี `interaction_id`)

| event | เมื่อไร | ข้อมูล |
|---|---|---|
| `ready` | หลังเชื่อมต่อ | `encoding`, `sample_rate`, `language`, `forwarding`, `model` |
| `partial` | ผู้โทรกำลังพูด (ทุก `ASR_PARTIAL_INTERVAL_MS`) | `text`, `language`, `duration`, `forwarded` (เมื่อเปิดส่งต่อ) ข้อความถอดจากต้นประโยคถึงปัจจุบัน แต่ละ partial มาแทน partial ก่อนหน้า |
| `final` | ผู้โทรเงียบเกิน `ASR_ENDPOINT_SILENCE_MS` หรือพูดเกิน `ASR_MAX_UTTERANCE_S` หรือ client ปิด stream | เหมือน `partial` |
| `pong` | ตอบ `{"action":"ping"}` | |
| `error` | ถอดเสียงล้มเหลว หรือส่งข้อความผิดรูปแบบ | `message` stream ยังเปิดต่อ |
| `closed` | สิ้นสุด stream | `end_call` |

**Client → server**

| เฟรม | ผล |
|---|---|
| binary | ข้อมูลเสียงตาม `encoding` และ `sample_rate` ขนาด chunk 20 ถึง 200 ms กำลังดี |
| `{"action":"end"}` | ถอดเสียงส่วนที่ค้าง ส่ง `closed` แล้วปิด |
| `{"action":"end","end_call":true}` | เหมือนด้านบน และเรียก `POST /api/v1/calls/{id}/end` ของ Middleware ด้วย (Widget ได้ `call_ended`) |
| `{"action":"ping"}` | ตอบ `pong` |

- ถ้า client ตัดการเชื่อมต่อเฉย ๆ บริการยังถอดและส่งต่อประโยคที่ค้างก่อนจบ แต่จะ **ไม่** เรียก `/end` (สายอาจเชื่อมต่อ stream ใหม่)
- partial ที่เกิดขณะกำลังถอดเสียงอื่นอยู่จะถูกข้าม เพื่อไม่ให้คิวสะสมเมื่อเครื่องช้า ส่วน `final` ไม่ถูกข้าม

**ตัวอย่าง (Python)**

```python
import asyncio, json, websockets

async def main(pcm_bytes):
    uri = "ws://127.0.0.1:5001/v1/stream/CALL-9042-DEMO?language=th"
    async with websockets.connect(uri) as ws:
        print(await ws.recv())                                  # ready
        for i in range(0, len(pcm_bytes), 3200):                # 100 ms ของ PCM16 16 kHz
            await ws.send(pcm_bytes[i:i + 3200])
        await ws.send(json.dumps({"action": "end"}))
        async for message in ws:
            print(message)                                      # partial / final / closed
```

---

## 5. การเชื่อมต่อกับระบบอื่น

| ระบบ | สิ่งที่ต้องทำ | สถานะ |
|---|---|---|
| CivicVoice API | รับข้อความที่ `POST /api/v1/calls/{id}/segments` อยู่แล้ว | ✅ ทดสอบแล้ว (ดูหัวข้อ 7) |
| Agent Widget | ไม่ต้องแก้ ได้ `transcript` และ `summary` จาก Middleware | ✅ ทดสอบด้วย WebSocket client จำลอง Widget จริงไม่ได้เปิดทดสอบ |
| Genesys Cloud CX | ต้องมีตัวกลาง (media gateway) ที่รับเสียงจาก Genesys AudioHook หรือ Media Streaming แล้วส่ง binary frame มาที่ `/v1/stream/{id}` | ❌ **ยังไม่ได้ทำ** AudioHook ใช้โปรโตคอลของตัวเอง (WebSocket พร้อมข้อความควบคุม) ไม่ใช่ binary ล้วน ๆ บริการนี้รับ G.711 µ-law 8 kHz ได้แล้ว จึงต่อได้ด้วยตัวแปลงบาง ๆ ที่ Watchara เป็นผู้ยืนยันรูปแบบกับ Genesys |
| ไฟล์ที่บันทึกไว้ | ใช้ `POST /v1/transcribe` ได้ทันที | ✅ |

---

## 6. การปรับใช้บน DGX 101

ตัวอย่าง systemd unit (ปรับ path ให้ตรงกับเครื่อง) รันคู่กับ `civicvoice.service` ที่ `scripts/setup_dgx101.sh` สร้างไว้

```ini
[Unit]
Description=BKK CivicVoice AI ASR (Faster-Whisper)
After=network.target

[Service]
User=gwplus
WorkingDirectory=/opt/BKK-CivicVoice-AI/src/asr
Environment=ASR_PRELOAD=true
ExecStart=/opt/BKK-CivicVoice-AI/src/asr/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 5001
Restart=always

[Install]
WantedBy=multi-user.target
```

- ผูกกับ `127.0.0.1` เพราะไม่มี Auth Middleware บนเครื่องเดียวกันเรียกผ่าน `BACKEND_URL=http://127.0.0.1:8000`
- รัน uvicorn **1 worker** (ค่าเริ่มต้น) แต่ละ worker โหลดโมเดลของตัวเอง
- **ปัญหาที่ต้องแก้ก่อนใช้งานบน DGX (ตรวจจาก PyPI แล้ว):** DGX เป็น ARM aarch64 (GB10) ล้อ (wheel) ของ CTranslate2 สำหรับ aarch64 บน PyPI รุ่น 4.6.2 เป็นรุ่นล่าสุดที่มี และ**ไม่ได้ลิงก์ไลบรารี CUDA** (cuBLAS/cuDNN) เลย หมายความว่า `pip install` บน DGX จะได้ ASR ที่ทำงานบน CPU ของ Grace โดยไม่มี error ทำให้ความเร็วต่ำกว่าสเปกมาก ตัวแปร `ASR_DEVICE=auto` จะเลือก `cpu` ให้เอง ต้องเปิด `/health` ดูฟิลด์ `device`
  - แนวทางที่ต้องเลือกและทดสอบบน DGX: (ก) build CTranslate2 จากซอร์สพร้อม CUDA บน aarch64 ซึ่งต้องมี CUDA toolkit, cuDNN และ CMake (ยังไม่ได้ตรวจว่า CTranslate2 รองรับ GPU ตระกูล Blackwell ของ GB10 หรือไม่) หรือ (ข) ใช้ runtime อื่นที่มี wheel CUDA สำหรับ aarch64 เช่น PyTorch กับ Whisper ของ Hugging Face (ช้ากว่าแต่ยืนยันได้ง่าย) ต้องเปลี่ยนโค้ด `engine.py` ก่อน
  - ผลทดสอบบนแล็ปท็อป (GTX 1050 4 GB) ใช้แทนไม่ได้ ตรวจพบ CUDA แต่โหลด cuBLAS ไม่ได้ เลยต้องใช้ CPU
- ต้องให้ DGX ดาวน์โหลดโมเดลจาก Hugging Face ได้ หรือดาวน์โหลดล่วงหน้าแล้วตั้ง `ASR_MODEL` เป็นโฟลเดอร์ในเครื่อง
- `scripts/setup_dgx101.sh` ยังไม่ได้ติดตั้งบริการ ASR (พอร์ต 5001) ต้องเพิ่ม venv, requirements ของ `src/asr` และ systemd unit ตามตัวอย่างด้านบน
- ชื่อ `large-v3-turbo` ถูกแปลงเป็น repo บน Hugging Face โดย `faster-whisper` (เป็นโมเดลแปลงโดยบุคคลที่สาม) ถ้าเครื่องจริงออกอินเทอร์เน็ตไม่ได้หรือต้องการควบคุมที่มา ให้ดาวน์โหลดล่วงหน้าแล้วตั้ง `ASR_MODEL` เป็นโฟลเดอร์ในเครื่อง

---

## 7. การทดสอบและผลที่ตรวจจริง

**ชุดเทสอัตโนมัติ** (รันจาก `src/asr`) ใช้ Whisper และ Middleware จำลอง จึงไม่ต้องดาวน์โหลดโมเดล

```bash
python -m pytest
```

ครอบคลุม: แปลง µ-law/PCM16/resample, การตัดประโยค (partial/final), การถอดเสียงและเลือกภาษา TH/EN, การกรองข้อความหลอนช่วงเงียบ, endpoint ทั้งหมด, สถานะ error, การส่งต่อไป Middleware (รวมกรณี Middleware ล่ม) และการถอดรหัสไฟล์จริงผ่าน PyAV

**การทดสอบ end-to-end กับโมเดลจริง** (26 พ.ย. 2026, Windows, CPU int8, Middleware จริงพร้อม LLM, WebSocket client จำลอง Widget) สร้างเสียงตัวอย่างด้วย edge-tts แล้วส่งผ่านบริการ ทดสอบทั้งโมเดล `small` และ `large-v3-turbo` ได้พฤติกรรมของ API เหมือนกัน

| กรณี | ผลที่ตรวจได้ |
|---|---|
| อัปโหลดเสียงไทย พร้อม `interaction_id` | HTTP 200, `forwarded.ok = true`, WebSocket ของสายนั้นได้ `transcript` และ `summary` (หมวด ท่อระบายน้ำ/น้ำท่วม, เขตคลองเตย, ความเร่งด่วนสูง) |
| อัปโหลดเสียงอังกฤษ ภาษา `auto` | ตรวจได้ `en` |
| อัปโหลดเสียงไทย ภาษา `auto` | ตรวจได้ `th` ไม่ถูกเดาเป็นภาษาอื่น |
| Stream PCM16 ภาษาไทย | ได้ `partial` แล้ว `final` ตามด้วย `closed` ทั้งสองถูกส่งต่อ และ Widget ได้ `transcript` ทั้งสองครั้งกับ `summary` |
| ไฟล์ที่ไม่ใช่เสียง | HTTP 422 พร้อมข้อความชัดเจน |

**ผลเทียบโมเดล** (ประโยคทดสอบ: "แถวซอยสุขุมวิท 50 มีท่อระบายน้ำแตก น้ำท่วมถนน อันตรายมาก ช่วยส่งคนมาดูหน่อยครับ", อัปโหลดไฟล์, ภาษา `auto`, CPU int8)

| โมเดล | ข้อความที่ได้ | เวลา (เสียง 7 วินาที) |
|---|---|---|
| `small` | "สุขุมวิท 50 มีท่อระบายน้ำแตกน้ำ ท่วงทะนนอันตรายมาก ..." (ขาด "แถวซอย", คำผิดหลายคำ) | ประมาณ 10 ถึง 13 วินาที |
| `large-v3-turbo` | "แถวซอยสุขุมวิท 50 มีท่อระบายน้ำแตกน้ำ ท่วงถนนอันตรายมาก ช่วยส่งคนมาดูหน่อยครับ" (ยังผิด 1 จุด: "น้ำท่วมถนน" ถูกถอดเป็น "น้ำ ท่วงถนน") | ประมาณ 26 ถึง 45 วินาที |

`large-v3-turbo` แม่นกว่าชัดเจนแต่บน CPU ช้ากว่าเวลาจริงหลายเท่า ใช้งานจริงต้องมี GPU

**บทเรียนที่พบระหว่างทดสอบ (แก้ในโค้ดแล้ว)**
- ครั้งแรกที่อัปโหลดไฟล์ ทุกไฟล์ได้ HTTP 500 เพราะ PyAV 19 เข้ากันไม่ได้กับ `faster-whisper` จึงกำหนด `av<19` (ดูหัวข้อ 2) เทสที่ใช้ Whisper จำลองมองไม่เห็นปัญหานี้ ต้องรันกับเสียงจริงถึงเจอ
- คำใบ้ `ASR_INITIAL_PROMPT` เป็นภาษาไทย เมื่อใช้กับเสียงอังกฤษ `large-v3-turbo` ช้าลงประมาณ 3 เท่า (34 วินาที เทียบกับ 99 วินาที) และในโหมด `auto` เคยถอดเป็นข้อความหลายภาษาที่อ่านไม่รู้เรื่อง ตอนนี้โหมด `auto` ตรวจภาษาก่อนโดยไม่ใส่คำใบ้ แล้วใส่คำใบ้เฉพาะเมื่อได้ภาษาไทย (ถอดซ้ำ 1 รอบ) ผลที่ตรวจหลังแก้: เสียงอังกฤษได้ประโยคถูกต้องโดยไม่ใช้คำใบ้ และเสียงไทยยังถอดครบ

**ข้อจำกัดของผลทดสอบนี้ (ต้องอ่านก่อนอ้างอิงตัวเลข)**
- เสียงที่ใช้เป็นเสียงสังเคราะห์ ไม่ใช่เสียงสายโทรศัพท์จริง และมีเพียง 2 ประโยค (ไทยและอังกฤษ) จึงบอกไม่ได้ว่าความแม่นยำจริงเป็นเท่าไร ยังไม่มีชุดทดสอบเสียงจริงพร้อมคำตอบถูกต้อง (ground truth)
- รันบน CPU จึงช้า ตัวเลข latency 100 ถึง 200 ms ใน [ai-models-specification.md](ai-models-specification.md) และ "ต่ำกว่า 150 ms" ใน infographic **ยังไม่ได้ยืนยัน** ต้องวัดบน GPU จริงก่อนนำไปใช้ใน Pitch

---

## 8. ข้อจำกัดที่ทราบแล้ว

| รายการ | รายละเอียด / ข้อแนะนำ |
|---|---|
| ยังไม่เชื่อม Genesys | ต้องมีตัวแปลงเสียงจาก AudioHook (ดูหัวข้อ 5) |
| Whisper ไม่ใช่โมเดล streaming | partial คือการถอดซ้ำตั้งแต่ต้นประโยค ยิ่งพูดยาวยิ่งใช้เวลา และ partial อาจเปลี่ยนคำจากครั้งก่อน บน CPU กับ `large-v3-turbo` ประโยคยาว 7 วินาทีใช้เวลาราว 24 วินาทีกว่าจะได้ `final` จึงไม่ใช่ real-time ต้องใช้ GPU |
| การตัดประโยคใช้ความดังเสียง | ไม่ใช่ VAD แบบโมเดล สายที่มีเสียงรบกวนสูงอาจตัดผิด ปรับด้วย `ASR_ENERGY_THRESHOLD` และ `ASR_ENDPOINT_SILENCE_MS` |
| ข้อความหลอนของ Whisper | ลดด้วย VAD และตัดช่วงที่โมเดลมั่นใจต่ำว่าไม่ใช่เสียงพูด แต่ไม่รับประกันว่าไม่มี |
| ไม่แยกผู้พูด | ทั้ง stream ถือเป็นผู้พูดเดียวตามค่า `speaker` ถ้าจะแยก caller/agent ต้องส่งเสียงแยกช่อง |
| ไม่มี Auth | ดูหัวข้อ 4 |
| ไม่มีการจำกัดจำนวน stream พร้อมกัน | ใช้ `ASR_MAX_CONCURRENCY` คุมการถอดเสียงพร้อมกันเท่านั้น ถ้าสายพร้อมกันเกินกำลังเครื่อง คิวจะช้าลง |
| ยังไม่มีการวัดความแม่นยำบนเสียงจริง | ต้องทำก่อนอ้างตัวเลขใน Pitch |
| GPU บนเครื่องพัฒนาใช้ไม่ได้ | GTX 1050 (4 GB) ถูกตรวจพบโดย CTranslate2 แต่โหลด `cublas64_12.dll` ไม่ได้ ทำให้ถอดเสียงล้มเหลว (HTTP 500) ระหว่างนี้ใช้ `ASR_DEVICE=cpu` ก่อน (ค่าเริ่มต้น `auto` จะเลือก GPU ถ้าตรวจพบ) ต้องติดตั้ง CUDA 12 runtime (cuBLAS/cuDNN) หรือ `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` แล้วตรวจอีกครั้งก่อนใช้ GPU |
