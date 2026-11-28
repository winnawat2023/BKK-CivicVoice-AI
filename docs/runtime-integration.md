# รัน BKK CivicVoice แบบเชื่อมบริการจริงในเครื่อง

## โค้ดที่ใช้

| Worktree | Branch | หน้าที่ |
| --- | --- | --- |
| `BKK-CivicVoice-AI` | `feature/fe-widget` | เว็บประชาชน, Agent Copilot, Citizen Tracking และบริการ SMS |
| `BKK-CivicVoice-backend` | `feature/backend` | Civic Middleware, Voicebot/RAG, TTS, คำร้องใน SQLite, WebSocket และ Faster-Whisper ดู `docs/api-guide.md` |
| `BKK-CivicVoice-genesys` | `feature/genesys` | Audio Connector รับ PCMU จาก Genesys Cloud และส่งเสียงตอบกลับ รองรับ Typhoon, OpenAI และ Gemini ดู `genesys/README.md` |

จากโฟลเดอร์แม่ เช่น `aiwar` ใช้คำสั่งด้านล่างสำหรับเครื่องใหม่ โครงการใช้ Python 3.11 สำหรับชุดคำสั่ง Windows นี้

```powershell
git clone --branch feature/fe-widget https://github.com/winnawat2023/BKK-CivicVoice-AI.git BKK-CivicVoice-AI
git -C BKK-CivicVoice-AI worktree add --track -b feature/backend ../BKK-CivicVoice-backend origin/feature/backend
git -C BKK-CivicVoice-AI worktree add --track -b feature/genesys ../BKK-CivicVoice-genesys origin/feature/genesys
```

ถ้ามีทั้งสาม worktree อยู่แล้ว ให้ใช้ `git pull --ff-only` ในแต่ละโฟลเดอร์ คู่มือ Backend อยู่ใน [API Guide](https://github.com/winnawat2023/BKK-CivicVoice-AI/blob/feature/backend/docs/api-guide.md) และ [ASR Service](https://github.com/winnawat2023/BKK-CivicVoice-AI/blob/feature/backend/docs/asr-service.md) ส่วนการตั้งค่ารับสายดู [Genesys Audio Connector](https://github.com/winnawat2023/BKK-CivicVoice-AI/blob/feature/genesys/genesys/README.md)

## เปิดใช้งานและตรวจสถานะ

| บริการ | URL |
| --- | --- |
| เว็บประชาชน | [127.0.0.1:8765](http://127.0.0.1:8765/) |
| โต๊ะเจ้าหน้าที่ | [127.0.0.1:8765/desk.html](http://127.0.0.1:8765/desk.html) |
| ติดตามคำร้องในเครื่อง | [127.0.0.1:8765/tracking/](http://127.0.0.1:8765/tracking/) |
| Backend และ Typhoon | [Health](http://127.0.0.1:8000/api/v1/health?check_llm=true) |
| Faster-Whisper | [Health](http://127.0.0.1:5001/health?check_backend=true) |
| Genesys Audio Connector | [Health](http://127.0.0.1:8088/healthz) |
| บริการ SMS | [Health](http://127.0.0.1:8766/api/sms/health) `disabled` ปิดส่ง, `mock` สำหรับทดสอบในเครื่อง |

จาก root ของ `BKK-CivicVoice-backend` เตรียมไฟล์ตั้งค่าและ dependencies ครั้งแรก ตรวจค่าใน `.env` ให้ตรงกับ LLM และ ASR ของเครื่องก่อนรัน

```powershell
python -m venv src/backend/venv
& src/backend/venv/Scripts/python.exe -m pip install -r src/backend/requirements.txt -r src/asr/requirements.txt pytest
if (!(Test-Path src/backend/.env)) { Copy-Item src/backend/.env.example src/backend/.env }
if (!(Test-Path src/asr/.env)) { Copy-Item src/asr/.env.example src/asr/.env }
```

```powershell
src\backend\venv\Scripts\python.exe -m uvicorn src.backend.main:app --host 127.0.0.1 --port 8000
```

เปิดอีก terminal ที่ `BKK-CivicVoice-backend/src/asr`

```powershell
..\backend\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 5001
```

การตั้งค่าในเครื่องนี้ใช้ Typhoon 1.5X 8B Instruct แบบ GGUF ผ่าน llama.cpp ที่ `127.0.0.1:8001` หลังเชื่อม DGX ตามค่าในเอกสารไม่ได้ ตั้ง `VLLM_URL=http://127.0.0.1:8001/v1/chat/completions` และ `VLLM_MODEL=typhoon-8b` พร้อมคีย์ของ instance ในไฟล์ `.env` ที่ถูก ignore ส่วน ASR ใช้ Faster-Whisper `large-v3-turbo` บน CPU แบบ int8 เปิด `ASR_PRELOAD=true` และเชื่อม Backend ที่พอร์ต 8000 ค่าเสียงไทยที่ทดสอบผ่านในเครื่องนี้คือ `th-TH-NiwatNeural` สำหรับ `THAI_TTS_VOICE` และ `TYPHOON_TTS_VOICE`

รัน Typhoon บนเครื่องนี้ด้วยไฟล์ที่ติดตั้งไว้ในโฟลเดอร์ Local AppData

```powershell
$runtime = Join-Path $env:LOCALAPPDATA 'BKK-CivicVoice'
& "$runtime\llama-b12811\llama-server.exe" --model "$runtime\models\typhoon-1.5x-8b-q4km.gguf" --alias typhoon-8b --host 127.0.0.1 --port 8001 --ctx-size 4096 --n-gpu-layers all --parallel 1 --api-key-file "$runtime\integration\llama-api-key.txt"
```

ที่ `BKK-CivicVoice-genesys/genesys` เตรียม dependencies และไฟล์ตั้งค่าครั้งแรก

```powershell
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -r requirements.txt pytest pytest-asyncio
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

ใช้ `AI_PROVIDER=typhoon`, `TYPHOON_BASE_URL=http://127.0.0.1:8001/v1`, `TYPHOON_STT_BASE_URL=http://127.0.0.1:5001/v1` และ `TYPHOON_VOICEBOT_URL=http://127.0.0.1:8000/api/v1/voicebot/converse` ตั้งคีย์สำหรับ AudioHook และ Typhoon ใน `.env` แล้วรัน

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8088
```

ให้ Connector ใช้ `TRANSCRIPT_WEBHOOK_FORMAT=civic_segments` และ `TRANSCRIPT_WEBHOOK_URL=http://127.0.0.1:8000/api/v1/calls/{interaction_id}/segments` เพื่อให้ข้อความผู้โทรและ AI เข้า Copilot ตาม Conversation ID การจบสายใน Architect ใช้ `POST /api/v1/calls/{interaction_id}/end` หลังโทรศัพท์วางจริง การสิ้นสุด Audio Connector อาจเป็นการส่งต่อสายให้เจ้าหน้าที่

จาก root ของ `BKK-CivicVoice-AI` เปิดเว็บและรันบริการ SMS ใน terminal แยก

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory src/frontend
```

```powershell
$smsPython = '../BKK-CivicVoice-backend/src/backend/venv/Scripts/python.exe'
& $smsPython -m pip install -r src/backend/requirements-sms.txt
if (!(Test-Path src/backend/sms.env)) { Copy-Item src/backend/sms.env.example src/backend/sms.env }
$env:SMS_MODE = "mock"
$env:SMS_PUBLIC_ORIGIN = "http://127.0.0.1:8765"
& ../BKK-CivicVoice-backend/src/backend/venv/Scripts/python.exe -m uvicorn sms_evidence:application --factory --app-dir src/backend --host 127.0.0.1 --port 8766
```

เปิดหน้าเว็บด้วย `127.0.0.1:8765` ให้ตรงกับ `SMS_PUBLIC_ORIGIN` หากต้องการปิดส่งให้กำหนด `$env:SMS_MODE = "disabled"` ก่อนรัน หากเปิดส่งจริงใช้ terminal ใหม่เพื่ออ่านค่าจาก `sms.env` ตาม [การตั้งค่า SMS](../README.md#sms-หลังยืนยันแจ้งปัญหา)

## เส้นทางจริงและขอบเขตปัจจุบัน

- **ประชาชนบนเว็บ** กด **ติดต่อเรา → เริ่มสนทนาบนเว็บ** และอนุญาตไมค์ เบราว์เซอร์จับช่วงพูดและส่งให้ Faster-Whisper ถอดเสียงเมื่อเว้นช่วง Voicebot ตอบเป็นเสียงอัตโนมัติ เมื่อ AI พูดจบ ไมค์พร้อมรับช่วงถัดไป กด **จบการสนทนา** เพื่อดูสรุปและช่องกรอกเบอร์มือถือ ยืนยันคำร้องก่อนส่ง SMS
- **ประชาชนโทรเข้า Genesys** ป๊อปอัปแสดงเบอร์ **02-096-6763** สำหรับโทรจากอุปกรณ์ เส้นทางรับสายนี้ต้องผูก DID กับ Inbound Flow ใน org `ark-insights` และตั้ง `Call Audio Connector` ให้ชี้ไปยัง WSS ที่ Genesys Cloud เข้าถึงได้ ใบรับรองต้องออกโดย public CA และคีย์ Audio Connector ต้องตรงกับค่าบนเซิร์ฟเวอร์
- **เจ้าหน้าที่** เปิด `/desk.html` เพื่อดูสายที่ส่ง Transcript เข้ามาหรือกรอก Conversation ID เอง เมื่อฝังใน Genesys ใช้ `/widget/?interaction_id=<Conversation ID>` พฤติกรรมส่งเขตปัจจุบันอัปเดตคำร้องใน Backend ส่วนการเชื่อมระบบปลายทางของสำนักงานเขตยังเป็นงานแยก
- **SMS** ผู้ให้บริการได้รับข้อความที่ประกอบจากเลขคำร้อง สรุป และพื้นที่ที่บันทึกแล้ว ผู้รับลิงก์ดูสถานะและเพิ่มรูป GPS หรือลิงก์แผนที่ในบริการ SMS ตามเลขคำร้อง การเปิดส่งจริงต้องตั้ง SMSKUB หรือ ThaiBulkSMS, HTTPS gateway และเบอร์ทดสอบตาม [README](../README.md#sms-หลังยืนยันแจ้งปัญหา)
- **ฟีเจอร์ที่รอสัญญา API** ได้แก่ คำแปลสด EN–TH, สคริปต์แนะนำ Tourist Assist, Duplicate Check และการส่งเสียง TTS จากปุ่มเจ้าหน้าที่เข้าคู่สาย โดย Agent Copilot เล่นเสียงตัวอย่างจาก Backend ได้

## ทดสอบอัตโนมัติ

จากโฟลเดอร์แม่ของทั้งสาม worktree

```powershell
Push-Location BKK-CivicVoice-AI
& ../BKK-CivicVoice-backend/src/backend/venv/Scripts/python.exe -m unittest discover -s src/tests -p 'test_*.py'
Pop-Location
Push-Location BKK-CivicVoice-backend
& src/backend/venv/Scripts/python.exe -m pytest -q src/backend/tests
Pop-Location
Push-Location BKK-CivicVoice-backend/src/asr
& ../backend/venv/Scripts/python.exe -m pytest -q tests
Pop-Location
Push-Location BKK-CivicVoice-genesys/genesys
& .venv/Scripts/python.exe -m pytest -q
Pop-Location
```

## ซ้อมเดโมทีละเส้นทาง

1. **Voice และ SMS จำลอง** เปิดเว็บประชาชน อนุญาตไมค์ แล้วพูดว่า “ไฟถนนดับสองดวงที่ถนนประชาสงเคราะห์ เขตดินแดง” เว้นช่วงให้ AI ตอบ ตรวจว่าข้อความฝั่ง AI ขึ้นหลังเสียงจบ กด **จบการสนทนา** แล้วเปิด **ระบุสถานที่เพิ่มเติม** ตรวจรายชื่อ 50 เขตและแก้รายละเอียด กด **ยืนยันแจ้งปัญหา** ตรวจเลขคำร้อง แล้วกรอกเบอร์มือถือทดสอบและกด **ส่ง SMS** ในโหมด `mock`
2. **หลักฐานในมือถือ** กด **เปิดลิงก์ SMS จำลอง** ตรวจเลขคำร้องเดียวกับหน้าสรุป ลองแชร์ GPS แนบ JPEG/PNG/WebP ไม่เกิน 5 MB และบันทึกลิงก์ Google Maps โหลดใหม่แล้วตรวจว่าทั้งสามรายการยังอยู่ โหมดนี้ใช้ Voicebot จริงกับฐานข้อมูลหลักฐานแยกจากโหมดส่งจริงและไม่ใช้เครดิต
3. **Agent Copilot และ Tracking** เปิด [โต๊ะเจ้าหน้าที่โหมดเดโม](http://127.0.0.1:8765/desk.html?mode=demo) เลือกเคสและตรวจที่ความกว้าง 400/450/500px ทดลองเพิ่ม Transcript ดูคำแปลและ Tourist Assist ของเคสตัวอย่าง กดส่งเขตและดู Timeline 4 ขั้นที่ [หน้าติดตามเดโม](http://127.0.0.1:8765/tracking/?mode=demo) ในเบราว์เซอร์เดียวกัน
4. **WebSocket และข้อมูลจริงในเครื่อง** รัน `python src/tests/simulate_call.py` จาก root ของ `feature/fe-widget` เพื่อจำลอง webhook เปิด Interaction ID `CALL-9042-DEMO` ในโต๊ะเจ้าหน้าที่เพื่อตรวจ Transcript และสรุป สคริปต์สร้างข้อมูลทดสอบใน Backend ที่กำลังรัน หากต้องการทดสอบโดยใช้ข้อมูลชั่วคราวให้รันชุด pytest ฝั่ง Backend
5. **Genesys และ SMS จริง** เมื่อ Cloud เชื่อมถึง Audio Connector และผูก DID แล้ว โทร **02-096-6763** และเปิด Conversation ID ใน Copilot สำหรับ SMS จริงให้ใช้เบอร์ที่อนุญาตและลิงก์ HTTPS ที่อนุมัติแล้ว ตรวจทั้งผลผู้ให้บริการรับคำขอ ข้อความที่ได้รับบนมือถือ และการบันทึกข้อมูลผ่านลิงก์ การส่งจริงใช้เครดิตและหลักฐานจะอยู่ในบริการ SMS จนกว่า Core Backend จะมี API รับหลักฐาน
