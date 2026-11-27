# แผนเชื่อม Frontend กับ Middleware API 2.0

อัปเดต 27 พฤศจิกายน 2569 ดู [คู่มือรันบริการจริงในเครื่อง](../../../../../../../../docs/runtime-integration.md) สำหรับการเชื่อม Frontend กับ `feature/backend` และ `feature/genesys` หน้าเว็บปกติใช้บริการจริงแล้ว ส่วนลำดับเดโมด้านล่างเก็บไว้สำหรับเปิดตัวอย่างแบบออฟไลน์

## เส้นทางเดโมที่ยืนยันล่าสุด

- **ประชาชน:** เปิด `/` → ติดต่อเรา → เริ่มสนทนา → จบและดูสรุป → ยืนยันแจ้งปัญหา → ขอ SMS หรือเปิด Tracking ของคำร้องเดโม ทั้งหน้า AI Voice และ Agent Copilot ใช้โลโก้ ARK Insights
- **เจ้าหน้าที่:** เปิด `/desk.html` ทดสอบ Agent Copilot ใน iframe หรือเปิด `/widget/?interaction_id=<Genesys Conversation ID>` เพื่อใช้กับสายจริง ปุ่มส่งสำนักงานเขตอยู่ฝั่งเจ้าหน้าที่
- **Tracking:** เปิดได้จากลิงก์ SMS จำลองหรือจาก AI Voice เดโม เบราว์เซอร์เดียวกันแชร์เฉพาะสถานะของเลขคำร้องตัวอย่างผ่าน localStorage เมื่อเจ้าหน้าที่ส่งเขต หน้าติดตามที่เปิดค้างจะอัปเดตตาม ปุ่มเริ่มเดโมใหม่ล้างสถานะเหล่านี้ คำพูดผู้ใช้ พิกัด และไฟล์รูปไม่ถูกเก็บใน localStorage

### AI Voice กับ API Guide

| ช่วง | API และพฤติกรรม |
|---|---|
| เปิดโหมดจริงในเครื่อง | `/?mode=live` ตรวจ `GET /api/v1/health?check_llm=false` ปกติชี้ไปที่ `http://127.0.0.1:8000` เมื่อ Frontend อยู่ที่พอร์ต 8765 |
| ถามตอบ | `POST /api/v1/voicebot/converse` ส่ง `message`, `language: th` และบทสนทนาก่อนหน้าโดยไม่มี `interaction_id` เพื่อยังไม่สร้าง Ticket |
| เสียงตอบ | ใช้ `tts_audio_url` ที่มาจาก origin ของ Backend และตรง endpoint `/api/v1/tts/synthesize` หากเล่นเสียงไม่ได้ยังอ่านคำตอบได้ |
| สรุป | `POST /api/v1/civic/classify` สรุปข้อความของผู้ใช้ ให้ตรวจสรุปและระบุสถานที่ก่อนยืนยัน |
| เปิดคำร้อง | ยืนยันแล้วจึงส่ง `interaction_id` ของรอบสนทนาไปยัง Voicebot หากเปิดบริการ SMS แยก จะเรียกผ่าน `/api/sms/confirm` เพื่อรับสิทธิ์ขอ SMS เมื่อ Backend ยืนยันเลขคำร้อง |

สิ่งที่ยังต้องเชื่อม ได้แก่ API ถอดเสียงสตรีมและรับสายผ่าน Genesys สำหรับเว็บประชาชน สัญญา WebSocket สำหรับ snapshot และผลแปล สคริปต์ช่วยตอบ การตรวจเคสซ้ำ Tracking สาธารณะจากสถานะจริง การแนบข้อมูลกลับเข้า Core Backend และการส่งเสียง TTS เข้าคู่สาย คู่มือ v2 ยังไม่กำหนด auth สำหรับเว็บสาธารณะ จึงใช้ `enableCitizenVoice: false` เป็นค่าเริ่มต้นภายนอกเครื่อง ต้องเปิดผ่าน HTTPS gateway ที่จำกัด endpoint และตรวจสิทธิ์ก่อนใช้งาน

อัปเดต 25 พฤศจิกายน 2569 · Branch `feature/fe-widget`

อ้างอิงไฟล์แนบ `api-guide.md` วันที่ 25 พ.ย. และ `openapi.json` เวอร์ชัน 2.0.0 ขอบเขตหน้าจอยึดบรีฟ Agent Copilot และ Tourist Assist เดิม

| งาน | สัญญาที่ใช้ | การทำงานฝั่ง Frontend |
|---|---|---|
| เปิด Agent Widget | `/ws/agent/{interaction_id}` | รับ Genesys Conversation ID จาก URL ค่าที่รองรับคือ `interaction_id`, `conversationId` และ `conversationid` ตรวจสายและไม่แสดงผลข้ามสาย |
| ข้อมูลสด | `connected`, `snapshot`, `transcript`, `summary`, `ticket`, `call_ended`, `error`, `pong` | รับ snapshot ใหม่เมื่อเชื่อมต่อ รองรับ partial/final ให้แสดงผลล่าสุด ล้างข้อความสดและ ANI เมื่อวางสาย รอทวน payload จริงกับ Backend |
| บันทึกและส่งเขต | `create_ticket` ผ่าน WS หากยังไม่มีเลขเรื่อง แล้ว `POST /api/v1/tickets/{ticket_id}/dispatch` | ใช้เลขเรื่องเดิมถ้ามี รอผลยืนยันก่อนแสดงว่าส่งแล้ว บล็อกการกดซ้ำ ไม่ส่ง create ซ้ำเมื่อผลไม่ชัดเจน |
| ดูคำร้องในเครือข่ายภายใน | `GET /api/v1/tickets/{ticket_id}` | แสดง timeline จาก `status`, `dispatched`, `dispatched_at`; ไม่อนุมานขั้นจากเวลา และไม่ใช้หน้า public ยิง API นี้ |
| ฟัง TTS | `GET /api/v1/tts/synthesize?text=…&lang=en` | ใช้ประโยคอังกฤษที่ตรวจแล้ว จำกัด 600 ตัวอักษร เล่นให้เจ้าหน้าที่ฟังในเบราว์เซอร์ |
| Tourist Assist | ยังไม่มี translation/script event ในเอกสารแนบ | รองรับช่องแสดงตัวอย่างและประโยคอังกฤษที่แก้เองได้ แยกคำแปล/สคริปต์ที่รอ contract ออกจากข้อความต้นฉบับ |
| SMS และการส่งหลักฐาน | `/api/sms/confirm`, `/api/sms/send`, `/api/sms/evidence` จากบริการ SMS แยก | แสดงปุ่มหลัง Backend 2.0 ยืนยันเลขคำร้อง ส่งลิงก์พร้อม token สำหรับเพิ่ม GPS รูป และลิงก์แผนที่ มีโหมดจำลองที่บันทึกข้อมูลได้โดยไม่ใช้เครดิต ข้อมูลอยู่ในบริการ SMS ตามเลขคำร้อง |
| TTS เข้าคู่สาย | API ปัจจุบันคืนไฟล์เสียงเท่านั้น | รอวิธีเล่นเสียงเข้าคู่สายและสถานะจาก Genesys ไม่ใช้ outbound stub แทน |

### สัญญาบริการ SMS หลังได้เลขคำร้อง

| Endpoint | พฤติกรรมในต้นแบบ |
| --- | --- |
| `GET /api/sms/health` | ตรวจความพร้อมของบริการ หากเข้าถึงไม่ได้ Frontend ยังยืนยันคำร้องผ่าน Voicebot ได้ |
| `POST /api/sms/confirm` | ส่งคำขอยืนยันไปยัง Voicebot 2.0 แล้วคืน `sms_grant` อายุ 30 นาทีเมื่อได้เลขคำร้อง |
| `POST /api/sms/send` | ใช้ `sms_grant` และเบอร์มือถือไทย จำกัดการส่งต่อคำร้องและต่อวัน ประกอบข้อความจากเลขคำร้อง สรุป และพื้นที่ที่บันทึก โหมด `mock` คืนข้อความและลิงก์จำลอง โหมดจริงจำกัดเฉพาะเบอร์ทดสอบและแสดงผลเมื่อ SMSKUB หรือ ThaiBulkSMS รับคำขอ |
| `GET /api/sms/evidence` และ `PUT /api/sms/evidence/{location,photo}` | ลิงก์ผู้รับเปิด `/tracking/?mode=evidence` และใช้ token อายุ 7 วันเพื่ออ่านหรือเพิ่มหลักฐานในคำร้องเดียว |

การซ้อมจากหน้าเว็บเดโมเปิดฟอร์มและลิงก์ตัวอย่างได้ โหมด `mock` ของบริการ SMS ใช้ทดสอบการบันทึกหลักฐานโดยไม่เรียกผู้ให้บริการ ส่วนการส่งจริงต้องมี Voicebot 2.0, HTTPS gateway, บัญชี SMSKUB หรือ ThaiBulkSMS และค่าใน `sms.env` ตาม [README](../../../../../../../../README.md#sms-หลังยืนยันแจ้งปัญหา) การแนบข้อมูลเข้า Core Backend รอ API รับหลักฐาน

Frontend ไม่เรียก Genesys webhook, ASR segments, จบสาย, patch สถานะ หรือ voicebot เพื่อเลียนแบบบริการฝั่งทีมอื่น การทดสอบ contract ใช้ fixture แยกจากข้อมูลจริง คู่มืออ้างไฟล์ `websocket-protocol.md` ซึ่งไม่ได้แนบและไม่พบใน branch ปัจจุบัน ตัวอย่าง envelope ของ WebSocket ที่ใช้ทดสอบเป็นตัวอย่างชั่วคราว รอทีมยืนยันก่อนเปิดการสร้างคำร้องผ่าน WS

## เตรียมเปิดใช้งาน

1. เสิร์ฟ `src/frontend` เป็น static assets ใช้ `/widget/?mode=demo` และ `/tracking/?mode=demo` เพื่อซ้อมโดยไม่เรียก API จริง
2. หลัง Backend ส่งมอบ ให้ตั้ง HTTPS สำหรับหน้า Widget และ WSS สำหรับ middleware ใช้ API origin ที่ทีมกำหนดใน `src/frontend/config.mjs`; ในเครื่องใช้ `apiBase=http://127.0.0.1:8000` ได้
3. ตรวจ `GET /api/v1/health?check_llm=false` แล้วเปิด `/widget/?interaction_id=<Genesys Conversation ID>` ตรวจ snapshot และเทียบ transcript/summary/ticket กับสายจริง ตรวจ reconnect, call ended, การส่งซ้ำ และทดสอบ TTS preview เป็นเสียงอังกฤษ
4. ขอ payload จริงของ WS โดยเฉพาะ `snapshot`, `summary`, `ticket_result` และ `create_ticket` ยืนยันว่าการสร้างคำร้อง idempotent ต่อสาย ก่อนเปิดค่าสำหรับฟีเจอร์นี้และซ้อม create → dispatch ในสายที่ยังไม่มี Ticket
5. เปิด `/tracking/?mode=internal&ticket=<Ticket ID>` เฉพาะในเครือข่ายภายในที่เข้าถึง API ได้ โหมดนี้ใช้ตรวจ contract ภายในเท่านั้น ก่อนเปิดหน้า public ต้องมี endpoint แบบจำกัดข้อมูลและ token, ยืนยันสถานะ/ส่งหลักฐานใบเดิม, และทดสอบลิงก์บนมือถือ
6. ตั้งค่าบริการ SMS แยกตาม README ทดสอบยืนยันคำร้อง → สร้างลิงก์ → บันทึก GPS รูป และลิงก์แผนที่ใน `SMS_MODE=mock` ก่อนเปิดทดสอบส่งจริงกับเบอร์ทีม ส่วนการเชื่อมหลักฐานกลับเข้าคำร้องหลักและ TTS เข้าคู่สายรอ Backend/Genesys

เกณฑ์รับงานรอบนี้: เดโมผ่านได้โดยไม่เสียเครดิต; ทดสอบ WebSocket และ REST กับ fixture ที่แยกจากเซิร์ฟเวอร์จริง; พร้อมตั้งค่าและ smoke test ทันทีเมื่อ API 2.0 ส่งมอบ การเปิดใช้จริงยังขึ้นกับผลตรวจ WS ทั้งสองฝั่ง, CORS/HTTPS, access control และ endpoint ที่เหลือ

ทดสอบด้วย Chrome และ fixture ทั้ง Agent Copilot ขนาด 380/400/450/500px, Tracking มือถือ, transcript แบบ partial/final, การเชื่อมต่อใหม่, จบสาย, REST ส่งเขต และตัวอย่างเสียง TTS เส้นทางประชาชนผ่านการทดสอบยืนยันคำร้องจาก Voicebot จำลอง เปิดลิงก์ SMS แบบ `mock` บันทึก GPS/รูป/ลิงก์แผนที่และอ่านผลหลังรีโหลด ดูภาพ [Agent Copilot](./designs/07-agent-copilot-browser-demo.png), [Citizen Tracking](./designs/08-citizen-tracking-browser-demo.png) และ [ป๊อปอัปขอ SMS](./designs/09-citizen-sms-browser-demo.png)
