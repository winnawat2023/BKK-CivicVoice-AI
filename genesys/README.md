# AI Voice ↔ Genesys Cloud Audio Connector (WSS bridge)

เซิร์ฟเวอร์ **WSS (WebSocket over TLS)** ที่ทำหน้าที่เป็น *Audio Connector server*
ของ Genesys Cloud และเชื่อมต่อเสียงแบบ two-way กับ AI แบบเรียลไทม์
รองรับ 3 backend เลือกได้ด้วย `AI_PROVIDER`:

- **OpenAI Realtime API** (`AI_PROVIDER=openai`, ค่าเริ่มต้น)
- **Google Gemini Live API** (`AI_PROVIDER=gemini`)
- **Typhoon self-hosted vLLM** (`AI_PROVIDER=typhoon`, cascade STT → Typhoon chat-completions → TTS)

```
ผู้โทร ── PSTN ──► Genesys Cloud ── WSS (AudioHook v2) ──► บริการนี้ ── WSS ──► OpenAI Realtime / Gemini Live
                        ▲                                     │
                        └──────── เสียง AI ตอบกลับ ◄───────────┘
```

> **สำคัญ:** Genesys Cloud เป็นฝั่ง *client* ที่ต่อ WSS เข้ามาที่เซิร์ฟเวอร์ของเรา
> เราไม่ได้เป็นฝั่งไปต่อหา Genesys

---

## สถาปัตยกรรม / protocol ที่รองรับ

- **AudioHook protocol v2** (Audio Connector feature) — text frame = JSON, binary frame = เสียง
- Media: **PCMU / G.711 µ-law / 8 kHz / mono** (เฉพาะ channel `external`)
- Flow: `open` → `opened` → binary audio ↔ (binary audio กลับ + `event`) → `close` → `closed`
- ควบคุม: `ping`/`pong`, `pause`/`paused`/`resume`/`resumed`, `update`, `dtmf`, `discarded`
- Events ที่ส่งกลับ Genesys: `barge_in`, `bot_turn_response`
- **ตรวจ HTTP Message Signature (RFC 9421, HMAC-SHA256)** ของ upgrade request

### เส้นทางเสียง

**OpenAI (ค่าเริ่มต้น)** — PCMU passthrough ไม่ต้อง resample/transcode
เพราะ OpenAI Realtime รองรับ `audio/pcmu` โดยตรง

| ทิศทาง | การแปลง |
|---|---|
| Genesys → OpenAI | binary PCMU 8k → base64 → `input_audio_buffer.append` |
| OpenAI → Genesys | `response.output_audio.delta` (PCMU 8k) → binary frame (paced) |

**Gemini Live** — Gemini เป็น PCM16 ล้วน จึงต้องแปลงเสียง

| ทิศทาง | การแปลง |
|---|---|
| Genesys → Gemini | PCMU 8k → PCM16 8k → resample 16k → `realtimeInput.audio` (`audio/pcm;rate=16000`) |
| Gemini → Genesys | `serverContent.modelTurn.inlineData` (PCM16 24k) → resample 8k → PCMU → binary frame (paced) |

outbound audio ถูก pace ให้ **ไม่ถี่เกินทุก 200 ms** และ frame ละ **≤ 64,000 bytes**
ตามข้อกำหนดของ Genesys (`GENESYS_SERVER_AUDIO_CHUNK_MS`)

---

## โครงสร้างโปรเจกต์

```
app/
  main.py                 # FastAPI app, WSS endpoint, auth
  config.py               # โหลดค่าจาก env/.env (pydantic-settings)
  audiohook/
    messages.py           # helper สร้างข้อความ + media negotiation
    signature.py          # verify/create HTTP Message Signature
    session.py            # state machine ของ session + audio pacer
  ai/
    realtime.py           # OpenAI Realtime client (bridge)
    gemini.py             # Gemini Live API client (BidiGenerateContent)
    audio.py              # G.711 µ-law codec + resampler
scripts/
  fake_genesys_client.py  # client จำลอง Genesys สำหรับทดสอบ local
tests/                    # unit tests (signature / audio / messages / AI bridges)
requirements.txt
.env.example
Dockerfile
```

---

## สิ่งที่ต้องมี

- Python 3.10+
- Genesys Cloud org ที่ติดตั้ง **Audio Connector** จาก AppFoundry และ activate แล้ว
- API key ของผู้ให้บริการ AI ที่เลือก:
  - **OpenAI** — key ที่ใช้ Realtime API ได้ (`sk-...`)
  - **Gemini** — key จาก [Google AI Studio](https://aistudio.google.com/apikey) (ขึ้นต้นด้วย `AIza...`)
- โดเมน + TLS certificate จาก **public CA** (Genesys ไม่รับ self-signed) สำหรับ production

---

## เริ่มต้นใช้งาน (local)

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
# แก้ .env: AI_PROVIDER + key ของ provider (OPENAI_API_KEY หรือ GEMINI_API_KEY),
#          GENESYS_API_KEY, GENESYS_CLIENT_SECRET
```

รันเซิร์ฟเวอร์ (โหมด HTTP ธรรมดาสำหรับ dev):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

ตรวจสุขภาพเซิร์ฟเวอร์: `http://localhost:8080/healthz`

### ทดสอบด้วย client จำลอง

เปิด terminal ที่สอง:

```bash
# แบบไม่ต้องตรวจ signature (สะดวกตอน dev)
python scripts/fake_genesys_client.py --url ws://localhost:8080/api/v1/audiohook/ws
```

ถ้าต้องการทดสอบ signature ให้ตั้ง `GENESYS_API_KEY` / `GENESYS_CLIENT_SECRET` ใน `.env`
แล้วรัน:

```bash
python scripts/fake_genesys_client.py \
  --url ws://localhost:8080/api/v1/audiohook/ws \
  --api-key change-me --client-secret change-me-too
```

client จะส่ง `open`, ส่งเสียงโทน 1 kHz เป็น PCMU, แล้ว `close`/รอ `closed`
พร้อมพิมพ์ข้อความที่ได้รับและจำนวน audio bytes ที่ได้กลับมา

> ถ้ายังไม่ตั้ง key ของ provider ที่เลือก เซิร์ฟเวอร์จะทำงานแบบ **protocol-only**
> (ตอบ `opened`/`closed` ได้ แต่ไม่มีเสียง AI) เหมาะสำหรับทดสอบ WSS/protocol ก่อน
> ดูสถานะได้ที่ `/healthz` (`ai_provider`, `ai_configured`)

---

## ตั้งค่า Genesys Cloud

1. **ติดตั้ง Audio Connector** จาก Genesys AppFoundry
2. ไปที่ **Admin → Integrations → Audio Connector → Configuration**
   - ตั้ง **API Key** และ **Client Secret** ให้ตรงกับ `GENESYS_API_KEY` / `GENESYS_CLIENT_SECRET`
   - ตั้ง **WebSocket URL** เป็น `wss://<your-domain>/api/v1/audiohook/ws`
     (`<your-domain>` ต้องมี certificate จาก public CA)
3. ไปที่ **Architect** แล้วเพิ่ม action **Call Audio Connector**
   - เลือก integration ที่ตั้งไว้
   - วาง action ใน inbound / in-queue / outbound flow ตามต้องการ
4. (ทางเลือก) ตั้ง **Audio Monitoring** ที่ queue หากใช้AudioHook Monitor

หลัง action ทำงาน Genesys จะต่อ WSS เข้ามาที่เซิร์ฟเวอร์นี้ แล้วเริ่ม `open` transaction

---

## ตั้งค่า AI backend

เลือก provider ด้วยตัวแปรเดียว:

```dotenv
AI_PROVIDER=openai   # หรือ gemini
```

### OpenAI Realtime

```dotenv
OPENAI_API_KEY=sk-...
OPENAI_REALTIME_MODEL=gpt-realtime
OPENAI_VOICE=alloy
OPENAI_AUDIO_FORMAT=pcmu
OPENAI_INSTRUCTIONS=You are a friendly and concise phone assistant...
BOT_GREETING=true
```

- `OPENAI_AUDIO_FORMAT=pcmu` (แนะนำ) — passthrough ไม่แปลงเสียง
- `OPENAI_AUDIO_FORMAT=pcm` — ใช้ PCM16 24 kHz แล้วให้เซิร์ฟเวอร์ resample 8k↔24k (เผื่อกรณีที่ต้องการ)
- `BOT_GREETING=true` — ให้บอททักทายก่อนเมื่อ session เปิด
- `barge_in`: เมื่อ OpenAI VAD ตรวจว่าผู้โทรมาเริ่มพูดระหว่างบอทกำลังพูด
  เซิร์ฟเวอร์จะส่ง event `barge_in` ให้ Genesys หยุดเล่นเสียงทันที และเคลียร์คิวเสียงที่ค้างอยู่

### Google Gemini Live

เอาคีย์จาก <https://aistudio.google.com/apikey> (เป็นคนละอันกับ OpenAI) แล้วตั้ง:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-3.8-live
GEMINI_VOICE=Kore
GEMINI_ENABLE_TRANSCRIPTION=true
GEMINI_SESSION_RESUMPTION=true
GEMINI_GREETING_PROMPT=
BOT_GREETING=true
```

- `GEMINI_MODEL` — ค่าเริ่มต้น `gemini-3.8-live` (model ที่ Google แนะนำสำหรับ voice agent)
  ถ้าบัญชี/ydc ยังไม่เปิด model นี้ ให้ลอง `gemini-3.1-flash-live-preview` หรือ
  `gemini-2.5-flash-native-audio-preview-12-2025` (เติม `models/` เองได้หรือไม่ก็ได้)
- `GEMINI_VOICE` — ชื่อ voice ของ Gemini เช่น `Kore`, `Puck`, `Charon`
- `GEMINI_ENABLE_TRANSCRIPTION=true` — เปิด input/output transcription
  เพื่อส่ง `bot_turn_response` กลับ Genesys (ปิดได้ถ้าไม่ต้องการ)
- **เสียง**: Gemini รับ PCM16 16 kHz และส่งออก PCM16 24 kHz เซิร์ฟเวอร์แปลงเป็น
  PCMU 8 kHz ให้อัตโนมัติ (ไม่ต้องตั้งค่าอะไรเพิ่ม)
- **barge-in**: Gemini ทำ VAD ฝั่ง server แล้วส่ง `serverContent.interrupted`
  เซิร์ฟเวอร์จะเคลียร์คิวเสียงและส่ง event `barge_in` ให้ Genesys
- **session ยาว**: Live API แบบ audio-only จำกัดประมาณ 15 นาที
  เปิด `GEMINI_SESSION_RESUMPTION=true` + `GEMINI_CONTEXT_WINDOW_COMPRESSION=true`
  เพื่อให้ reconnect ต่อบทสนทนาเดิมได้ (สูงสุด `GEMINI_RECONNECT_ATTEMPTS` ครั้ง)
- `pause`: เมื่อ Genesys ส่ง `pause` เซิร์ฟเวอร์จะส่ง `audioStreamEnd` ให้ Gemini
  เพื่อ flush เสียงที่ค้างและปิด turn อย่างรวดเร็ว

> หมายเหตุ: ตอนนี้ยังไม่ได้ทำ tool/function calling ของ Gemini หรือ OpenAI
> (`toolCall` จะถูก log แล้วข้าม) — ต่อยอดได้ใน `app/ai/`

### Transcript webhook

หลังจบแต่ละ turn (caller หรือ bot) เซิร์ฟเวอร์ POST JSON ไปที่ webhook:

```dotenv
TRANSCRIPT_WEBHOOK_URL=https://your-server.example.com/transcript
TRANSCRIPT_WEBHOOK_FORMAT=turn
TRANSCRIPT_WEBHOOK_TIMEOUT=5.0
TRANSCRIPT_WEBHOOK_BEARER_TOKEN=
TRANSCRIPT_FALLBACK_DIR=transcripts
```

สำหรับ Agent Copilot ให้ใช้ `TRANSCRIPT_WEBHOOK_FORMAT=civic_segments` และตั้ง `TRANSCRIPT_WEBHOOK_URL=http://127.0.0.1:8000/api/v1/calls/{interaction_id}/segments` เมื่อ Backend อยู่เครื่องเดียวกัน หลังจบ turn แต่ละครั้ง Connector จะส่ง `speaker`, `text`, `is_final` และ `ani` ให้ Backend กระจายต่อผ่าน WebSocket หัวข้อด้านล่างแสดงรูปแบบค่าเริ่มต้น `turn`

```json
{
  "interaction_id": "CALL-9042-DEMO",
  "ani": "0847685368",
  "dnis": "02-096-6763",
  "channel": "voice",
  "role": "caller",
  "transcript": "แถวซอยสุขุมวิท 50 มีท่อระบายน้ำแตก",
  "timestamp": "2026-11-25T10:00:00+00:00"
}
```

- ค่ามาจาก **Call Audio Connector** input variables ที่ตั้งใน Architect
  (`parameters.inputVariables`): `interaction_id`, `ani`, `dnis`
- ถ้าไม่ได้ตั้ง input variables จะ fallback ไปที่ `parameters.conversationId`,
  `participant.ani`, `participant.dnis`
- `channel` เป็น `"voice"` เสมอ, `role` เป็น `"caller"` หรือ `"bot"`
- ถ้า webhook ส่งไม่สำเร็จ (หรือไม่ได้ตั้ง URL) และตั้ง `TRANSCRIPT_FALLBACK_DIR`
  ไว้ จะ append ลง `transcripts/transcripts-YYYYMMDD.jsonl` แทน

---

### Typhoon / vLLM self-hosted (cascade)

?????????? Typhoon ?? vLLM ??? OpenAI-compatible (?????? BKK-CivicVoice-AI) ???????? vLLM ???? chat-completions (text-only) ????????????? cascade: **STT -> Typhoon LLM -> TTS**

```dotenv
AI_PROVIDER=typhoon
TYPHOON_BASE_URL=http://127.0.0.1:8001/v1
TYPHOON_API_KEY=
TYPHOON_MODEL=typhoon-8b
TYPHOON_INSTRUCTIONS=...

# STT (OpenAI-compatible /v1/audio/transcriptions ???? faster-whisper-server/speaches)
TYPHOON_STT_BASE_URL=http://127.0.0.1:5001/v1
TYPHOON_STT_MODEL=large-v3-turbo
TYPHOON_STT_LANGUAGE=th

# TTS: edge_tts (?????? BKK-CivicVoice-AI) ???? openai (/v1/audio/speech)
TYPHOON_TTS_PROVIDER=edge_tts
TYPHOON_TTS_VOICE=th-TH-PremwadeeNeural
```

????????:
- `TYPHOON_BASE_URL` ???????????? endpoint ??? OpenAI-compatible (`/v1/chat/completions`) ??? vLLM
- `TYPHOON_STT_BASE_URL` ??????????????????? STT ????????? `/v1/audio/transcriptions` (?????? faster-whisper ?????????? speaches/faster-whisper-server)
- `edge_tts` ????????????????????????????????; ?????????? self-hosted ????????????? `TYPHOON_TTS_PROVIDER=openai` ?????? `TYPHOON_TTS_BASE_URL` ????? TTS server ????????? `/v1/audio/speech`
- Bridge ?????? VAD ??????? (energy + silence) ?????????????? `TYPHOON_VAD_*`

---

## ขึ้น production (WSS/TLS)

Genesys ต้องการ `wss://` ที่ certificate ออกโดย public CA เลือกได้ 2 แบบ:

**1) Terminate TLS ที่ load balancer / reverse proxy (แนะนำ)**
- nginx / ALB / Cloudflare รับ TLS แล้ว proxy มาที่ container port 8080
- ต้อง forward headers เดิมทั้งหมด (โดยเฉพาะ `Host`, `Signature`, `Signature-Input`, `X-API-KEY`)
  เพราะ signature ถูกคำนวณจาก `@authority` (Host) และ headers เหล่านี้
- ถ้าอยู่หลัง proxy ต้องมั่นใจว่า uvicorn มองเห็น `Host` ที่ Genesys ใช้จริง

**2) Terminate TLS ในตัวแอป/uvicorn**

ตั้งค่าใน `.env`:

```dotenv
HOST=0.0.0.0
PORT=8443
SSL_CERTFILE=/certs/fullchain.pem
SSL_KEYFILE=/certs/privkey.pem
# SSL_CA_CERTS=/certs/ca.pem   # optional
```

แล้วรันตามปกติ (แอปจะเปิด `wss://` ให้อัตโนมัติเมื่อมี cert+key):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8443
# หรือ
python -m app.main
```

หรือส่งผ่าน CLI โดยตรง:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8443 \
  --ssl-keyfile /certs/privkey.pem --ssl-certfile /certs/fullchain.pem
```

> สำหรับ Genesys Cloud จริง cert ต้องออกโดย **public CA** (self-signed ใช้ไม่ได้กับ Genesys)
> self-signed ใช้ได้เฉพาะ dev/test ภายใน

### ทดสอบ WSS แบบ local (self-signed)

```bash
# สร้าง cert dev ไว้ใน certs/ (ถูก gitignore)
# จากนั้นรันเซิร์ฟเวอร์ด้วย SSL_CERTFILE/SSL_KEYFILE หรือ --ssl-* 

# ทดสอบด้วย fake client (ข้ามการตรวจ cert เฉพาะ dev)
python scripts/fake_genesys_client.py \
  --url wss://localhost:8443/api/v1/audiohook/ws \
  --insecure --seconds 1
```

Docker:

```bash
docker build -t genesys-audio-bridge .
docker run --env-file .env -p 8443:8443 -v /path/to/certs:/certs genesys-audio-bridge
```

### ความปลอดภัย

- เก็บ `GENESYS_CLIENT_SECRET` และ API key ของ AI (`OPENAI_API_KEY` / `GEMINI_API_KEY`)
  ใน secret manager ไม่ใช่ใน repo
- เปิด `AUDIOHOOK_VERIFY_SIGNATURE=true` เสมอใน production
- **ห้าม** เปิด `AUDIOHOOK_ALLOW_UNSIGNED=true` ใน production
- พิจารณา rate limit / connection limit ที่ reverse proxy
- ข้อความ `info` ใน `disconnect` ต้องไม่มี PII

---

## ทดสอบ

```bash
pip install -r requirements-dev.txt
pytest -q
```

unit tests ครอบคลุม: signature round-trip/tamper/expiry, µ-law codec, resampler,
media negotiation, connection probe detection, OpenAI event mapping และ
Gemini Live event mapping (audio conversion, barge-in, transcript, resume handle)

---

## ข้อจำกัด / งานต่อยอด

- รองรับเฉพาะ **PCMU 8 kHz** (ยังไม่รองรับ L16 ของ Audio Connector)
- ยังไม่มี **reconnect/handover** (protocol v2 รองรับ `reconnect` + `continuedSessions`;
  ต้องมี state store เช่น Redis เพื่อ stitch เสียงข้าม instance)
- ยังไม่ทำ `pause`/`resume` แบบ server-initiated (โครงสร้างพร้อม แต่ยังไม่เรียกใช้)
- ยังไม่รองรับ **connection probe แบบเต็มรูปแบบ** สำหรับ multi-tenant (ปัจจุบันข้าม AI เมื่อ probe)
- ยังไม่ทำ DTMF → AI (ปัจจุบันแค่ log; ต่อยอดได้โดยส่งเป็น text item ให้ผู้ให้บริการ AI)
- Transcript ส่งออกได้ผ่าน webhook หลังจบแต่ละ turn (`TRANSCRIPT_WEBHOOK_URL`); ถ้า webhook fail หรือไม่มี URL แต่ตั้ง `TRANSCRIPT_FALLBACK_DIR` จะเก็บ fallback เป็น JSONL ในเครื่อง (ยังไม่มี DB/retry worker)
- ค่า `interaction_id` / `ani` / `dnis` ใน webhook อ่านจาก Architect **Call Audio Connector** input variables (`parameters.inputVariables`) ก่อน; ถ้าไม่มีจะ fallback ไปที่ `conversationId` / `participant.ani` / `participant.dnis`
- ยังไม่รองรับ tool/function calling ของทั้ง OpenAI Realtime และ Gemini Live

---

## Troubleshooting

| อาการ | สาเหตุ/แนวทาง |
|---|---|
| Genesys ต่อไม่ติด / TLS error | certificate ต้องออกโดย public CA, ต้องเป็น `wss://`, ตรวจ SNI/hostname |
| 401/403 ตอน handshake | `GENESYS_API_KEY`/`GENESYS_CLIENT_SECRET` ไม่ตรง, หรือ proxy ตัด/แก้ headers |
| signature FAILED | `Host` ที่เซิร์ฟเวอร์เห็นไม่ตรงกับที่ Genesys เซ็น (มักเกิดหลัง proxy) |
| เปิด session แล้วเงียบ | ยังไม่ตั้ง key ของ provider (`OPENAI_API_KEY` / `GEMINI_API_KEY`), `AI_PROVIDER` ไม่ตรง, หรือ `BOT_GREETING=false` และผู้โทรยังไม่พูด |
| Gemini ขึ้น `setup failed` | model ไม่มีสิทธิ์/ชื่อผิด (ลอง `gemini-3.1-flash-live-preview`), key ผิด, หรือเครื่องออกอินเทอร์เน็ตไม่ได้ |
| Gemini หลุดหลัง ~15 นาที | ปิด `GEMINI_SESSION_RESUMPTION` ไว้; เปิดเป็น `true` และให้ `GEMINI_RECONNECT_ATTEMPTS` > 0 |
| เสียงขาด/หน่วง | ปรับ `GENESYS_SERVER_AUDIO_CHUNK_MS` (ต่ำลง = latency ต่ำลง แต่ถี่ขึ้น) |
| ปรับระดับเสียงไม่ได้ | ทั้ง PCMU และ Gemini PCM16 เป็น mono; ตรวจว่าไม่ได้ส่ง stereo |

---

## อ้างอิง

- Genesys AudioHook Protocol: <https://developer.genesys.cloud/devapps/audiohook/protocol-reference>
- Genesys Audio Connector overview: <https://help.genesys.cloud/319987>
- OpenAI Realtime API: <https://platform.openai.com/docs/guides/realtime>
- Gemini Live API overview: <https://ai.google.dev/gemini-api/docs/live>
- Gemini Live API WebSocket reference: <https://ai.google.dev/api/live>
- Gemini API key (Google AI Studio): <https://aistudio.google.com/apikey>
- Official Genesys reference server: <https://github.com/GenesysCloudBlueprints/audioconnector-server-reference-implementation>
