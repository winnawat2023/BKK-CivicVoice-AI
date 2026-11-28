# แผน Frontend Widget & Real-time Integration

> ขอบเขตหน้าจอและลำดับการส่งเรื่องในฉบับนี้ถูกแทนที่ด้วย `agent-copilot-tracking-plan-v2.md` ตามบรีฟ Team Lead ล่าสุด: Agent Copilot iframe เป็นหน้าหลัก, เจ้าหน้าที่กดส่งเขต และประชาชนใช้ Tracking ผ่าน SMS/LINE ภาพ/flow popup AI ด้านล่างเก็บเป็นบันทึกข้อเสนอเดิม

วันที่: 23 พฤศจิกายน 2569 (2026), เวลาอ้างอิง Asia/Bangkok  
ผู้รับผิดชอบ: Aitthiphon — Member 4  
Branch: `feature/fe-widget` (ผู้ใช้กำหนด)  
ดีไซน์ที่ผู้ใช้เลือก: **02 Soft Blue** — ขาว–น้ำเงิน ดู modern และเป็นมิตร เข้ากับเว็บไซต์อื่นได้ง่าย  
สถานะ: ข้อเสนอสำหรับพิจารณา ยังไม่ใช่สัญญา API ที่ทีมอนุมัติหรือระบบโทรที่ทดสอบแล้ว  
Repository: https://github.com/winnawat2023/BKK-CivicVoice-AI  
โค้ดฐานที่ตรวจ: `main` commit `d3a555d5ebdbc4c80b463f4b22d669146e5c232e`

## 1. ผลลัพธ์ที่ต้องการ

พัฒนา Widget แบบลอยที่มุมขวาล่างของเว็บไซต์ กดเปิดหน้าต่างแล้วกดปุ่ม “คุยกับ AI” เพื่อสนทนากับ AI Voice ภาษาไทยผ่านไมโครโฟนและลำโพงบนเว็บไซต์ เชื่อมสายเข้าระบบ Genesys ของทีม โดยไม่ต้องกรอกเบอร์โทรหรือเปิดแอปโทรศัพท์ AI รับฟังคำถามและตอบเป็นเสียงจากข้อมูลที่ทีมเตรียมไว้ (ชุดข้อมูลตัวอย่าง/ฐานความรู้ RAG)

ผู้ใช้ยืนยันแล้วในแชตว่าต้องการโทรผ่านไมโครโฟนบนเว็บไซต์ เมื่อใช้งานครั้งแรก เบราว์เซอร์อาจขออนุญาตใช้ไมโครโฟน จึงนิยาม one-click เป็นหนึ่งปุ่มเริ่มสายหลังได้รับสิทธิ์แล้ว ไม่รับประกันว่าครั้งแรกจะไม่มีหน้าต่างขอสิทธิ์หรือเวลารอคิว

ลำดับหลักตามคำชี้แจงล่าสุดของผู้ใช้: เปิด popup → เริ่มคุยกับ AI Voice → AI ตอบจากข้อมูลที่เตรียมไว้และรวบรวมรายละเอียด → จบบทสนทนา → แสดงสรุปเรื่อง/สถานที่/เขตให้ตรวจสอบ → กด “ส่งเรื่องเข้าเขต” → แสดงผลการส่งและเลขเรื่อง สำหรับการถามข้อมูลทั่วไปที่ไม่มีเรื่องร้องเรียน ให้ AI ตอบจบโดยไม่ส่งเรื่องเข้าเขต

เอกสาร `docs/requirements.md` §1.2 และ §4 ระบุ AI เป็นด่านแรก และ `inception/requirements-analysis/requirements.md` FR5 ระบุให้ตอบเฉพาะชุดข้อมูลที่เตรียมไว้ หากไม่มีข้อมูลให้บอกตรงๆ และเสนอโอนหาเจ้าหน้าที่มนุษย์ ส่วนปุ่มส่งเขตในเอกสารเดิมอยู่ในมุมมองเจ้าหน้าที่ ข้อเสนอนี้เพิ่มขั้นตรวจสรุปและกดส่งหลังคุย AI ใน popup ตามคำชี้แจงล่าสุด โดยยังคง Agent Copilot สำหรับกรณีส่งต่อมนุษย์

หน้าประชาชนแสดงได้เฉพาะบทสนทนาและสรุปของ session ตนเอง ส่วนหน้าที่เจ้าหน้าที่ล็อกอินแสดงข้อมูลตามสิทธิ์ ไม่ต้องมีเจ้าหน้าที่มนุษย์เข้าร่วมทุกสาย และไม่ต้องโอนสายให้มนุษย์ก่อนสรุปหรือกดส่งเรื่อง

## 2. สิ่งที่มีอยู่จริงและช่องว่าง

| สิ่งที่ตรวจ | พฤติกรรมปัจจุบัน | งานที่ต้องเพิ่ม |
|---|---|---|
| `src/frontend/widget/index.html` | HTML + Tailwind CDN เป็นหน้าจอเต็ม | Launcher มุมขวาล่าง, popup, responsive, การโทร |
| WebSocket client | ใช้ `CALL-9042-DEMO` ตายตัวและ `ws://hostname:8000` | Config API/WS URL, conversation context, WSS, reconnect, ตรวจข้อมูล |
| Live update | รับ event `live_update` แล้วแสดงผล | แยกสถานะสาย/ข้อมูล/การเชื่อมต่อ, ป้องกันข้อมูลผิดสาย |
| ปุ่ม dispatch | เรียก `alert()` ด้วยข้อความสำเร็จและเขตตายตัว | ส่งคำขอจริง, ป้องกันกดซ้ำ, แสดงผลตาม Backend acknowledgement |
| Backend | มี webhook, list tickets และ `/ws/agent/{interaction_id}` | สัญญาส่งต่อเขต, รายละเอียดตาม interaction, auth และ sync หลัง reconnect |
| WS รับคำสั่ง | บันทึก log เท่านั้น | หากใช้ส่งคำสั่งต้องมี handler/ack; ข้อเสนอนี้ใช้ HTTP สำหรับ dispatch |
| `src/tests/simulate_call.py` | ยิง POST 2 เคส, พิมพ์ผล, ไม่ตรวจ WS และไม่ทำให้ process fail เมื่อผิด | CLI scenarios, assertions, timeout, exit code, isolation ของหลายสาย |
| การโทร | ยังไม่มี browser voice integration | ยืนยัน guest Web Call → Genesys AI Voice flow กับ Member 2 และทดสอบเสียงสองทาง |
| AI / ticket | Keyword mock, district 10 เขตและ fallback คลองเตย; สร้าง ticket แม้เป็น inquiry | Member 3 ต้องยืนยัน unknown district, inquiry และกติกาส่งต่อ |

README แนะนำเปิดไฟล์ HTML โดยตรง แต่เมื่อเปิดด้วย `file://` ค่า hostname อาจว่าง แผนจึงใช้เว็บเซิร์ฟเวอร์ในเครื่องและระบุ Backend URL ชัดเจน

## 3. ขอบเขตหน้าจอ

### 3.1 Citizen Call Widget

- ปุ่มลอยมีไอคอนโทรศัพท์และคำว่า “คุยกับ AI”; วางห่างขอบประมาณ 20–24px และเผื่อ safe area
- เปิด popup กว้างประมาณ 360–400px สูงตามเนื้อหา มีปุ่มปิดและหัวข้อชัดเจน
- บนมือถือใช้ความกว้าง viewport ลบขอบ 16px สองด้าน กำหนดความสูงสูงสุดและเลื่อนเนื้อหาได้
- ปุ่มหลักขนาดใหญ่ “เริ่มคุยกับ AI”; ระหว่างมีสายเปลี่ยนเป็นชุดควบคุม “ปิดไมค์” และ “จบการสนทนา”
- State: idle → requesting microphone → connecting → conversing → summarizing → review → submitting → submitted; แยก error พร้อมข้อความแก้ไข กรณี inquiry จบที่แสดงคำตอบ/สรุปโดยไม่ต้อง dispatch ส่วน queued ใช้เมื่อ provider รอเชื่อมต่อหรือโอนเข้าคิวมนุษย์จริง
- ระหว่างคุยแสดง “AI กำลังฟัง”, “AI กำลังประมวลผล”, “AI กำลังตอบ” ตาม event ที่ Backend ส่งมา ไม่ใช้ animation เป็นหลักฐานว่า AI ตอบจริง
- หลังคุยเสร็จแสดงสรุป 3 ประเด็น: ปัญหาหรือคำขอ / สถานที่และเขต / ความเร่งด่วนและหน่วยงานปลายทาง ก่อนเปิดปุ่ม “ส่งเรื่องเข้าเขต” สำหรับเรื่องร้องเรียน
- ถ้าจบสายก่อน AI สรุปสำเร็จ ให้รอผลสรุปหรือแสดงข้อความให้ลองใหม่ ไม่ตีความ ended ว่าส่งเรื่องแล้ว
- ถ้าถามข้อมูลทั่วไปให้ AI ตอบจากชุดข้อมูลที่เตรียมไว้ หากไม่มีข้อมูลต้องแจ้งว่าไม่มีข้อมูล ไม่แต่งคำตอบ และเสนอส่งต่อเจ้าหน้าที่ตามเอกสารเดิม
- สถานะ connected ต้องมาจาก telephony provider จริง จับเวลาเมื่อ provider ยืนยันสายแล้ว
- ไมโครโฟนถูกปฏิเสธ, ไม่พบอุปกรณ์, คิวไม่พร้อม, เชื่อมต่อหมดเวลา และสายหลุดต้องมีข้อความที่อ่านเข้าใจ
- พับ popup ระหว่างคุยได้ โดย launcher แสดง “กำลังสนทนา”; การพับไม่วางสายและไม่ทำลาย audio session
- ไม่เปิดไมโครโฟนหรือเริ่มสายจากการเปิดหน้าเว็บ แสดงสรุปและการส่งเรื่องเฉพาะ session ของผู้ใช้รายนั้น ไม่เปิดข้อมูลสนทนาหรือคำสั่งจัดการงานของเจ้าหน้าที่ให้ผู้ใช้ทั่วไป

### 3.2 Agent Copilot

- แสดงสถานะสายและสถานะข้อมูลสดแยกกัน: สายอาจยังคุยได้ขณะ WebSocket reconnect
- แสดง transcript ภาษาไทยและ AI summary: ปัญหา / สถานที่หรือเขต / ความเร่งด่วนพร้อมข้อความกำกับ
- แสดง Ticket ID, เขตเป้าหมาย, action แนะนำ และ SLA เฉพาะข้อมูลที่ Backend ส่งมา; ไม่คาดเดาเขตเมื่อไม่มีข้อมูล
- ถ้าข้อมูลยังไม่พอหรือเขตไม่ยืนยัน ให้ตรวจหรือแก้ไขเขตก่อนส่ง; เปิดปุ่ม one-click เมื่อข้อมูลพร้อม
- ปุ่ม dispatch มีสถานะพร้อมส่ง / กำลังส่ง / ส่งสำเร็จ / ส่งไม่สำเร็จ พร้อมคงข้อมูลเดิมเมื่อล้มเหลว
- ใน Genesys จริงแสดงเป็น embedded panel เต็มกรอบ iframe เพื่อไม่เกิด popup ซ้อน popup; ในเว็บไซต์ของทีมใช้ floating launcher ได้
- `mode=agent` เป็นการเลือก layout เท่านั้น Backend ต้องตรวจสิทธิ์ทุกครั้ง ไม่ถือ query parameter เป็นการล็อกอิน

### 3.3 Accessibility และรูปแบบ

- ภาษาไทยเป็นหลักและมีอังกฤษกำกับเฉพาะคำที่จำเป็น; body 16px และโหมดประชาชนตั้งเป้า 18px
- พื้นที่แตะอย่างน้อย 44px ปุ่มโทรประมาณ 52–56px; ตรวจ contrast ข้อความอย่างน้อย 4.5:1
- ใช้ keyboard เปิดปิดและสั่งโทรได้, มีชื่อปุ่มสำหรับ screen reader, focus เห็นชัดและกลับ launcher เมื่อปิด
- ถ้า popup เป็น non-modal อย่าล็อก focus ทั้งหน้า; ถ้าบนมือถือทำ modal ให้จัด focus ตาม dialog
- แจ้งเฉพาะการเปลี่ยนสถานะสำคัญด้วย live region ไม่อ่านข้อความ transcript ทุกคำซ้ำ
- render transcript และข้อมูลจาก server ด้วย `textContent`/DOM ที่ปลอดภัย แทน interpolation ผ่าน `innerHTML`
- ใช้ CSS แยกขอบเขตของ widget เพื่อไม่ให้ Tailwind preflight เปลี่ยนหน้าตาเว็บไซต์ที่ฝัง

## 4. ข้อจำกัด Genesys ที่ต้องปิดก่อนลงมือทำการโทร

Interaction Widget เป็นส่วนแสดงแอปตาม interaction ใน Genesys Agent Workspace; ไม่ได้ทำให้เว็บไซต์สาธารณะโทรได้โดยตัวมันเอง [G1]

เอกสาร Genesys Cloud WebRTC SDK ที่ตรวจระบุว่ารองรับ softphone ของ business user/agent ที่ยืนยันตัวตน และยังจัด guest Click-to-Call ไว้ในรายการไม่รองรับ [G2] จึงห้ามสมมติว่าแค่ติดตั้ง SDK นี้แล้วประชาชนจะโทรเข้าได้

Member 2 ต้องเลือกและพิสูจน์เส้นทาง guest Web Call ที่ใช้ได้กับ org ของทีม เช่น connector ที่รองรับ Genesys ซึ่งมีสิทธิ์ใช้งานแล้ว หรือ WebRTC/SIP gateway ที่ทีมมี ผู้ให้บริการหนึ่งอธิบายความสามารถ Web Call จากเว็บไซต์เข้าสู่ Genesys [G3] แต่ยังไม่ถือว่าทีมซื้อ มีสิทธิ์ หรือมี custom UI API ให้เรียกใช้

เงื่อนไขก่อนต่อ UI การโทรจริง:

1. ระบุ provider/gateway, deployment/region, ค่าใช้จ่ายหรือสิทธิ์เดโม และ queue/flow ปลายทาง
2. มีตัวอย่าง guest call จากเบราว์เซอร์เข้า Genesys AI Voice flow พร้อมเสียงสองทาง: ได้ยินคำตอบ AI จากข้อมูลที่เตรียมไว้ พูดโต้ตอบต่อเนื่องและจบสายได้; ทดสอบโอนหา Agent มนุษย์แยกเป็นกรณีเสริม
3. ได้ API สำหรับเริ่ม/จบ/ปิดไมค์และรับสถานะสาย รวมถึงข้อจำกัดการตกแต่ง UI; ถ้าไม่มี API ควบคุมต้องปรับดีไซน์ตามความสามารถ provider
4. ระบุวิธีผูก session ของผู้โทรกับ `conversationId` เดียวกับ webhook และ Agent Widget; ห้าม map ด้วยเลขโทรศัพท์หรือเดาสายล่าสุด
5. ทดสอบ microphone และ audio playback บน HTTPS/localhost, permission ใน iframe และเครือข่ายที่ใช้เดโม

ระหว่างรอเส้นทางโทร สามารถพัฒนา UI และ simulator ผ่าน adapter ได้ โดยแสดง “โหมดจำลอง” ชัดเจน การจำลองไม่นับเป็นหลักฐานว่าโทรผ่าน Genesys จริงแล้ว และไม่เปลี่ยนความต้องการผู้ใช้เป็น `tel:` โดยอัตโนมัติ

## 5. Integration contract ที่เสนอให้ตกลงกับทีม

### 5.1 Runtime configuration

กำหนด `apiBaseUrl`, `wsBaseUrl`, `mode`, `demoMode` และ telephony provider config ที่เปิดเผยได้ ส่วน Agent รับ conversation context จากการฝังใน Genesys แล้ว map เป็น `interaction_id` ของ Backend หลังตรวจรูปแบบ

ใช้งานจริงผ่าน HTTPS และ WSS ตาม environment อย่า hardcode localhost หรือพอร์ต production ลง component

### 5.2 WebSocket

คงเส้นทางปัจจุบัน `/ws/agent/{interaction_id}` และ `live_update` เพื่อไม่ทำลายของเดิมในรอบแรก เพิ่ม adapter แปลง payload เป็น view model ของ UI

ฟิลด์ที่มีอยู่: `ticket_id`, `interaction_id`, `caller_ani`, `transcript`, `intent`, `category`, `district`, `urgency`, `summary`, `suggested_action`, `sla_days`, `status`, `created_at`

ฟิลด์ที่เสนอเพิ่มภายหลังการตกลง: `schema_version`, `event_id`, `sequence`, `occurred_at`, `summary_points` และ event สำหรับ `call_state`, `ai_state`, `summary_ready`, `ticket_dispatched`, `heartbeat` ความคืบหน้าการโทรต้องมาจาก telephony provider/Backend จริง ส่วน `summary_ready` ระบุสรุปฉบับพร้อมตรวจและส่ง แยกจากสรุประหว่างคุยที่ยังแก้ไขได้

- ตรวจ JSON, ชนิดฟิลด์และ interaction ก่อน render; unknown event ต้องไม่ทำให้หน้าเสีย
- แยก event ตามสาย, ทิ้งข้อมูลสายเก่าหลังเปลี่ยน interaction และยกเลิก socket/listener เดิม
- Reconnect แบบ exponential backoff พร้อม jitter เช่น 1/2/4/8/16 วินาที สูงสุด 30 วินาที พร้อมข้อความสถานะ
- หลัง reconnect ขอ snapshot ตาม interaction จาก Backend ก่อนรับข้อมูลต่อ เพื่อไม่พลาด event ช่วงหลุด
- Backend เพิ่ม event id/sequence เมื่อจำเป็นต่อ dedupe และ ordering; ห้ามอ้างว่ารองรับ replay ในเวอร์ชันปัจจุบัน
- การล่มของ socket รายหนึ่งต้องไม่ทำให้ webhook ทั้งรายการล้ม; Member 3 ดูแลการ cleanup/broadcast และการแยกข้อมูลแต่ละสาย

### 5.3 การส่งเรื่องเข้าเขต

ข้อเสนอ API ใหม่ที่ยังไม่มีใน `main.py`: `POST /api/v1/tickets/{ticket_id}/dispatch` พร้อม `Idempotency-Key` และข้อมูล `district`, `interaction_id`, `expected_version` (ถ้าใช้ versioning)

Backend ตรวจสิทธิ์ให้ตรงผู้ส่ง: popup ประชาชนต้องผูก session กับเรื่องของตนเอง ส่วน Agent Copilot ใช้ agent authorization ทั้งสองแบบตรวจความสัมพันธ์ ticket/interaction, สรุปที่พร้อมแล้ว, intent ที่ส่งต่อได้, เขต และคำขอซ้ำ แล้วตอบ ticket/status/district ที่บันทึกสำเร็จ ต้องตกลง contract ฝั่งประชาชนกับ Member 3 เพิ่ม เพราะ endpoint เดิมยังไม่มี flow นี้ หากระบบเขตเป็น stub ต้องตอบ `delivery_mode: demo` และ UI แสดง “บันทึกการส่งต่อจำลองแล้ว”

แยกคำว่า “บันทึกคำขอส่งต่อแล้ว” ออกจาก “สำนักงานเขตรับเรื่องแล้ว” ถ้า endpoint เพียง enqueue ต้องแสดง pending และรอ downstream acknowledgement ก่อนบอกว่าปลายทางรับจริง ส่วน ticket creation ยังคงอยู่ใน webhook ตามโค้ดเดิม ไม่สร้าง ticket ใหม่จากปุ่ม dispatch ซ้ำ

เมื่อ request timeout ให้ตรวจสถานะคำขอเดิมหรือ retry ด้วย idempotency key เดิม แทนการสร้างรายการส่งต่อใหม่ การกดครั้งเดียวหมายถึงส่งข้อมูลที่ตรวจพร้อมแล้ว ไม่บังคับเปิด confirmation ซ้ำทุกครั้ง

## 6. แบ่งงานและการส่งมอบ

| งาน | เจ้าของ | สิ่งส่งมอบและเกณฑ์ตรวจ |
|---|---|---|
| W0: พิสูจน์ browser voice | Watchara + Peerapun + Aitthiphon | Guest browser → Genesys AI Voice → คำตอบเสียงจากข้อมูลที่เตรียมไว้ มีเสียงสองทางและ ID ที่ map กันได้ |
| W1: ดีไซน์/สถานะ | Aitthiphon | ใช้ 02 Soft Blue ที่ผู้ใช้เลือก ขยาย mobile และ error states ก่อนสร้าง component |
| W2: Popup shell | Aitthiphon | เปิด/พับ/ปิดได้, keyboard ได้, ไม่ทับเนื้อหาเกินกรอบ, ไม่รีเซ็ตสาย |
| W3: Telephony adapter | Aitthiphon + Watchara | start/mute/end + provider events + microphone errors; สนทนากับ AI Voice ตาม W0 |
| W4: Realtime data | Aitthiphon + Peerapun | สถานะฟัง/ตอบของ AI, transcript, summary_ready หลังคุย, reconnect + snapshot |
| W5: Dispatch | Peerapun ทำ API, Aitthiphon ทำ UI | ตรวจสรุปหลังคุย AI แล้วกดส่งเขต, session authorization, loading/ack/error, ไม่สร้างคำขอซ้ำ |
| W6: Simulator | Aitthiphon | CLI scenarios, HTTP/WS assertions, fail exit code, ผลลัพธ์อ่านง่าย |
| W7: Full demo | ทั้งทีม | เส้นทางโทรจริงและโหมดจำลองทดสอบแยกกัน, บทเดโมและวิดีโอสำรอง |

ไฟล์พัฒนาที่เสนอ: ขยาย `src/frontend/widget/` เป็น shell/stylesheet และโมดูล `config`, `state`, `telephony-adapter`, `realtime-client`, `ticket-client` ตามความจำเป็น คง HTML/JavaScript + Tailwind เพื่อใช้โค้ดเดิมได้ก่อน ไม่เพิ่ม framework โดยไม่มีเหตุผล

Build Tailwind เป็น CSS ภายในโครงการและเก็บฟอนต์ที่จำเป็นในเครื่อง เพื่อลด dependency ต่อ CDN ในวันเดโม ขอบเขตนี้ไม่รวมสร้าง LLM/STT, IVR หรือระบบรับเรื่องของสำนักงานเขตใหม่ทั้งหมด

## 7. ตารางเป้าหมาย 23–30 พฤศจิกายน 2569

| วันที่ | เป้าหมาย |
|---|---|
| 23 พ.ย. | Clone/สำรวจ, ยืนยันใช้ 02 Soft Blue แล้ว, นัดตกลง browser voice และสัญญาข้อมูล; เริ่ม W0 ก่อน |
| 24 พ.ย. | พิสูจน์ W0, ตกลง provider และ dispatch/snapshot contract; ทำ shell และ layout |
| 25 พ.ย. | UI ประชาชน/เจ้าหน้าที่และทุกสถานะหลักพร้อม review; ให้ตรง deadline Widget ในเอกสารทีม |
| 26 พ.ย. | Realtime client และ dispatch UI ต่อ API; ทดสอบโทรจริงถ้า provider พร้อม |
| 27 พ.ย. | Simulator และชุด failure scenarios พร้อม; ตรวจ permission, reconnection และหลายสาย |
| 28 พ.ย. เวลา 14:00 | เป้าหมาย integration ร่วมทีม: โทรผ่านเว็บ → AI Voice ตอบจากข้อมูล → จบและสรุป → ตรวจและกดส่งเขต พร้อมหลักฐานเวลา |
| 29 พ.ย. | ซ้อมซ้ำ แก้ blocker ทำวิดีโอสำรองและเตรียมไฟล์ local ให้ครบ |
| 30 พ.ย. | Smoke test, ซ้อมบทเดโม, เผื่อเวลาส่งงานตามกำหนดทีม |

เป็นตารางเสนอจากเอกสารทีม ยังไม่ได้สร้างนัดหรือแจ้งสมาชิก เอกสารเดิมเรียก 28 พ.ย. 2569 ว่า “วันศุกร์” แต่วันที่จริงตรงวันเสาร์ จึงอ้างวันที่และเวลาเป็นหลักและให้ทีมยืนยันนัด

หาก W0 ยังไม่ผ่านวันที่ 24 ให้ยกเป็นความเสี่ยงต่อการโทรจริงทันที พร้อมทำ W1/W2/W4/W6 ต่อบน mock adapter; ห้ามนับการยิง webhook ว่าเป็นการทดสอบเสียงสำเร็จ

## 8. Simulator และแผนตรวจรับ

เสนอ CLI: `python src/tests/simulate_call.py --base-url http://127.0.0.1:8000 --interaction-id DEMO-001 --scenario complaint --repeat 5` ตัวเลือกเหล่านี้เป็นงานที่จะพัฒนา ยังไม่ใช่คำสั่งที่สคริปต์ปัจจุบันรองรับ

Simulator ต้องเชื่อม WS และรอพร้อมก่อนยิง webhook จากนั้น assert HTTP status, schema, ticket/interaction ตรงกัน และได้รับ event ภายใน timeout; เคสใหม่สร้าง interaction แยก ไม่อิง ID ตายตัว

| เคส | สิ่งที่ต้องเห็น |
|---|---|
| Complaint ปกติ | AI รับรายละเอียด → summary_ready หลังคุย → ตรวจสรุปและเขต → กดส่ง; ไม่ส่งต่อจาก partial transcript |
| Inquiry ในชุดข้อมูล | ได้คำตอบจากข้อมูลที่เตรียมไว้และเสียงตอบกลับ; จบได้โดยไม่สร้างรายการส่งเขต |
| Inquiry นอกชุดข้อมูล | AI แจ้งว่าไม่มีข้อมูล ไม่สร้างคำตอบเอง และเสนอส่งต่อมนุษย์ตามข้อกำหนด |
| จบสายก่อนสรุปพร้อม | UI รอสรุปหรือแสดงข้อผิดพลาด; ปุ่มส่งยังไม่พร้อมและไม่ส่งอัตโนมัติ |
| ไม่ทราบเขต/ข้อมูลว่าง | UI ขอข้อมูลเพิ่ม ไม่ส่งเข้าเขต fallback เงียบๆ |
| 2 สายพร้อมกัน | Widget A ไม่แสดงข้อมูลสาย B; เปลี่ยนสายแล้วข้อมูลไม่ค้าง |
| WebSocket หลุด/กลับมา | ข้อความ reconnect, snapshot ล่าสุดกลับมา, ไม่สร้าง socket ซ้อน |
| Event ซ้ำ/ลำดับผิด/JSON เสีย | UI ไม่ crash และไม่ย้อนสถานะด้วยข้อมูลเก่า |
| Dispatch กดซ้ำ/timeout/HTTP 500 | ไม่สร้างรายการซ้ำ, ไม่แสดงสำเร็จลวง, retry ได้ |
| Transcript มี HTML/script | แสดงเป็นข้อความ ไม่ execute |
| ปิดไมค์/วางสาย/permission denied | ทดสอบใน browser กับ provider; Simulator HTTP พิสูจน์เสียงส่วนนี้ไม่ได้ |

ตั้งเป้า UI อัปเดตภายใน 2 วินาทีหลัง Backend ส่ง event วัดแยกจากเวลาที่ใช้ STT/LLM และเก็บตัวอย่างอย่างน้อย 20 events รายงาน p50/p95 เพื่อเห็นความผันผวน สำหรับการตอบด้วยเสียง ให้ทดสอบเกณฑ์เดิม FR5/NFR1 แยกต่างหาก: เริ่มคำตอบภายใน 2 วินาทีหลังผู้ใช้พูดจบในกรณีชุดข้อมูลที่รองรับ HTTP/WS simulator ไม่ใช่หลักฐานผ่านเกณฑ์เสียงนี้ ยังไม่มีผลวัดจริง

ตามแนวปฏิบัติทีม ใช้ TDD กับ logic สำคัญและรันชุดทดสอบเดิมก่อน merge ตั้งเป้า coverage อย่างน้อย 80% ตาม `memory/team.md` พร้อมรายงานว่าครอบคลุมส่วนใด ตรวจ manual เรื่องเสียง, iframe, keyboard และ mobile ควบคู่กัน เป้าหมายซ้อมคือเดโมปกติครบ 10 รอบติดโดยไม่มี uncaught error และ fault scenarios กู้คืนได้ ไม่อ้างว่าการทดสอบรับประกันระบบจะไม่ล่มทุกกรณี

## 9. ลำดับเดโมประมาณ 3 นาที

1. เปิดเว็บไซต์ กด launcher แล้วกด “เริ่มคุยกับ AI”; อนุญาตไมโครโฟนหากยังไม่เคยอนุญาต
2. ถามข้อมูลที่อยู่ในชุดข้อมูลเตรียมไว้ ได้ยิน AI ตอบผ่านเสียง; แสดงว่าระบบให้ข้อมูลได้โดยไม่ต้องรอมนุษย์
3. ทดสอบอีกบทสนทนาด้วยตัวอย่างปัญหาไฟถนนดับในเขตคลองเตย ให้ AI รวบรวมรายละเอียดแล้วจบบทสนทนา
4. Popup แสดงสรุป 3 ประเด็นและเขต ตรวจข้อมูลแล้วกด “ส่งเรื่องเข้าเขต” ครั้งเดียว แสดง Ticket ID และผลตอบรับตามระดับการเชื่อมต่อจริง
5. หากต้องการสาธิตทางออกเพิ่มเติม ให้ทดสอบคำถามนอกชุดข้อมูลแล้วส่งต่อมนุษย์แยกจากเส้นทางหลัก; ทดสอบ fault แสดง WS reconnect โดยไม่อ้างว่าเสียงขาดพร้อมกัน

เตรียมสคริปต์จำลองและวิดีโอที่ติดป้ายชัดเจนเป็นทางเลือกเมื่อเส้นทางโทรจริงใช้ไม่ได้ ไม่สลับโหมดเงียบๆ และใช้ข้อมูลสมมติในการซ้อม

## 10. ตัวอย่างดีไซน์

ผู้ใช้เลือก **02 Soft Blue** เมื่อ 23 พฤศจิกายน 2026 ให้ใช้เป็นแนวทางพัฒนาทั้ง popup ประชาชนและ Agent Copilot เพราะขาว–น้ำเงินดู modern เป็นมิตร และเข้ากับเว็บไซต์อื่นได้ง่าย ใช้พื้นขาว ปุ่มหลักน้ำเงิน การ์ดโค้งและสีอ่อนตามภาพอ้างอิง โดยรักษาปุ่มโทรให้เด่นและอ่านข้อความไทยได้ง่าย

ดู `design-notes.md` และภาพใน `designs/` ภายในโฟลเดอร์นี้ ทั้งสามแบบเป็นภาพแนวคิด ไม่ใช่ภาพระบบที่รันสำเร็จแล้ว เก็บ 01 Civic Minimal และ 03 Night Console ไว้เป็นตัวอย่างประกอบ ส่วนการพัฒนาใช้ 02 Soft Blue ภาพเดิมยังเขียนปุ่ม “โทรหาเจ้าหน้าที่” และแยกสรุปไว้ฝั่ง Agent จึงอ้างอิงเฉพาะ visual style ต้องเปลี่ยนข้อความเป็น AI Voice และเพิ่มหน้าสรุป/ตรวจ/ส่งหลังคุยตามคำชี้แจงล่าสุดก่อนพัฒนา

## 11. แหล่งอ้างอิง

- เอกสารทีม: `README.md`, `docs/requirements.md`, `docs/work-assignment.md`, `docs/battle-plan-timeline.md`
- ตรวจซ้ำตามคำชี้แจงผู้ใช้: `.kiro/specs/bkk-civic-connect/requirements.md`, `.kiro/specs/bkk-civic-connect/design.md`, `inception/requirements-analysis/requirements.md` (FR5, FR6, FR7), `inception/user-stories/stories.md` (US1.1, US1.6, US1.7)
- โค้ดจริง: `src/backend/main.py`, `src/frontend/widget/index.html`, `src/tests/simulate_call.py`
- บันทึกเดิม: `inception/refined-mockups/design-system-mapping.md`, `interaction-spec.md`, `aidlc/spaces/default/memory/team.md`
- [G1: Genesys — Set up an Interaction Widget integration](https://help.genesys.cloud/articles/set-up-an-interaction-widget-integration/) ตรวจ 23 พ.ย. 2026
- [G2: Genesys Cloud WebRTC SDK — README](https://github.com/MyPureCloud/genesys-cloud-webrtc-sdk/blob/develop/README.md) ตรวจ 23 พ.ย. 2026
- [G3: TrueEngage — Web Call Video](https://kb.trueengage.com/genesys-cloud/web-call-video) เอกสารจากผู้ให้บริการ ใช้เป็นตัวอย่างช่องทางที่ต้องตรวจสิทธิ์และ API เพิ่ม ไม่ใช่ข้อสรุปเลือกซื้อ

## 12. สถานะการส่งมอบครั้งนี้

Clone repository, ตรวจโค้ด/เอกสาร, จัดทำแผนและสร้างภาพแนวคิด 3 แบบแล้ว งานครั้งนี้ไม่ได้เปลี่ยนโค้ดแอป ติดตั้ง dependencies รันระบบโทร หรือทดสอบ integration จริง และไม่ใช่การอนุมัติหรือเลื่อน checkpoint เดิมของ AI-DLC
