# แผนเพิ่มเติม: Agent Copilot + Citizen Tracking + Notification

**อัปเดต 25 พ.ย. 2569** ใช้ [แผนเชื่อม Middleware API 2.0](./frontend-api-integration-plan.md) สำหรับสัญญา API และขั้นทดสอบต้นแบบล่าสุด ต้นแบบมีป๊อปอัป AI Voice สำหรับประชาชนพร้อมปุ่มขอ SMS หลังยืนยันเลขคำร้อง ส่วนเอกสารฉบับนี้เก็บแนวทางเดิมสำหรับการรับสายของเจ้าหน้าที่และเหตุผลที่เลือก SMS เป็นช่องทางหลัก

วันที่ตรวจข้อมูล: 23 พฤศจิกายน 2026 (Asia/Bangkok)  
Branch: `feature/fe-widget`  
สถานะ: แผนเสนอและภาพแนวคิด ยังไม่ได้สร้างบัญชีผู้ให้บริการ ส่งข้อความจริง หรือทดสอบระบบ Genesys/DGX

## 1. ขอบเขตล่าสุดที่ใช้พัฒนา

อ้างอิงบรีฟจาก Team Lead [B1] ที่อ่านตรงจาก GitHub รวมกับคำสั่งล่าสุดในแชต ให้ใช้แผนนี้แทนขอบเขตหน้าจอใน `implementation-plan.md` ฉบับก่อน:

- **P0: Agent Copilot Widget** ฝังใน Genesys Agent Desktop เป็น iframe กว้าง 400–500px (ตรวจเพิ่มที่ 380px) เจ้าหน้าที่เป็นผู้กดบันทึก/ส่งเขต
- **Tourist Assist ตามบรีฟเพิ่ม:** ซับอังกฤษ–ไทยคู่กัน, ประโยคตอบอังกฤษพร้อมคำอ่านไทย และปุ่มให้ AI ตอบเสียงอังกฤษเข้าคู่สาย รายละเอียดและเกณฑ์ตรวจอยู่ใน `tourist-assist-plan.md` โดยพิสูจน์ media path ตั้งแต่ต้น
- **P1: Citizen Tracking Web** เว็บมือถือที่เปิดจาก SMS หรือ LINE OA เป็นหน้าเดียวกัน ไม่ต้องสร้างแอปมือถือใหม่
- **P1: SMS notification** ช่องทางหลักที่เสนอสำหรับบริการประชาชน โดย LINE OA เป็นทางเลือกสมัครใจและช่องทางทดสอบฟรี
- **P2: Executive Dashboard** ทำเป็นภาพ/ข้อมูลประกอบ pitch หลังเส้นทางหลักผ่าน ไม่แสดง KPI ที่ยังไม่ได้วัดว่าเป็นผลจริง
- **Citizen AI Voice:** ป๊อปอัปมุมขวาล่างบนเว็บประชาชน สรุปเรื่องให้ตรวจก่อนยืนยัน หลังได้เลขคำร้องจึงส่ง SMS ขอพิกัดหรือรูปได้

AI Voice ที่ตอบจากชุดข้อมูลเตรียมไว้ยังเป็นความสามารถของระบบเบื้องหลัง ไม่ต้องบังคับโอนทุกสายให้มนุษย์ แต่หน้าจอที่ Member 4 ต้องทำอันดับแรกคือ Agent Copilot สำหรับสายที่เจ้าหน้าที่ดูแล และ Tracking สำหรับประชาชน

ข้อมูล Inbound Test จากทีม: **02-096-6763 / +66-2-096-6763**, org **ark-insights** เป็นเบอร์ทดสอบระบบจำลอง 1555 ไม่ใช่หมายเลข SMS ผู้รับหรือหลักฐานว่าหมายเลขนี้ส่ง SMS ได้ ผู้รับ SMS ใช้เบอร์มือถือที่ยืนยันจาก Caller ANI/สอบถามผู้โทร ส่วนเบอร์บ้านหรือ Caller ID ที่ไม่พร้อมต้องมีทางแจ้งเลขเรื่องด้วยเสียง

## 2. ลำดับทำงานของระบบและจุดเดโม

ประชาชนโทรเข้าเบอร์ทดสอบ → Genesys รับสาย/ดำเนิน AI Voice flow หรือส่ง Agent ตามบริบท → ฝั่ง AI แปลงเสียงและสรุป → Backend ส่ง event → Copilot แสดงข้อมูลสาย → เจ้าหน้าที่ตรวจสรุป/เขตและกดบันทึกพร้อมส่ง → ส่งลิงก์ติดตามให้ประชาชน → เปิด Tracking / เพิ่ม GPS / แนบรูป → อัปเดตข้อมูลในคำร้องและ Copilot

ตำแหน่งไม่ชัดสามารถส่งคำขอ GPS/รูปก่อน dispatch ได้ โดยใช้ reference ของ interaction/draft ที่ Backend ออกให้ ข้อมูลที่ประชาชนส่งต้องกลับไปยัง draft/คำร้องเดิม ไม่สร้างคำร้องอีกใบ ห้ามเริ่มส่ง SMS เพียงเพราะมี partial transcript ใหม่

## 3. Wireframe ของ Agent Copilot

ใช้ Clean Pro ต่อจาก Soft Blue: พื้นขาว, ตัวอักษร Navy `#0F172A`, ปุ่มหลักน้ำเงิน, Emerald `#10B981` สำหรับสถานะ/สำเร็จ, Cyan `#06B6D4` สำหรับ AI ใช้ Sarabun ภาษาไทยเป็นหลัก สีอ่อนเป็นพื้น card และตรวจ contrast ใน implementation

ลำดับจากบนลงล่างใน iframe:

1. **Header:** โลโก้ BKK CivicVoice AI, badge `ark-insights`, สถานะ Call และ AI/WS แยกกัน, interaction ID, ANI สำหรับเจ้าหน้าที่
2. **Live transcript:** ป้ายผู้พูด `[1555 Agent]` / `[ประชาชน]` และสีต่างกัน, timestamp, สถานะ partial/final, highlight ถนน/ซอย/เขต/สถานที่จาก entity offsets ที่ Backend ระบุ
3. **AI insight:** สรุป 3 ประเด็น, category จากรายการ 21 หมวดที่ทีมตกลง, district/หน่วยงาน, urgency CRITICAL/HIGH/NORMAL, SLA ที่เขียนว่า “คาดการณ์”
4. **Duplicate notice:** ระบุว่า “อาจซ้ำ”, จำนวนและระยะ/ช่วงเวลาที่ตรวจ, เปิดรายละเอียดเพื่อให้เจ้าหน้าที่ตัดสิน ไม่รวมเคสอัตโนมัติ
5. **Action footer:** ปุ่ม “1-Click บันทึกคำร้อง & ส่งสำนักงานเขต” เด่นที่สุด, ปุ่มรอง “ส่ง SMS ขอพิกัด / รูปภาพ”, feedback ส่งสำเร็จ/ล้มเหลว/กำลังทำงาน

สำหรับสายภาษาอังกฤษ ให้ transcript แสดงต้นฉบับ EN และคำแปล TH คู่กัน และเพิ่ม Tourist Assist card ระหว่าง Insight กับ Action Zone: ประโยคอังกฤษ / ความหมายไทย / คำอ่านไทย / preview / “1-Click ให้ AI ตอบเสียงภาษาอังกฤษแทน” แยก local preview ออกจากเสียงที่ส่งเข้าคู่สายจริงตาม `tourist-assist-plan.md`

ทำ transcript เป็นส่วนเลื่อนภายในและหยุด auto-scroll เมื่อเจ้าหน้าที่เลื่อนอ่านข้อความเก่า มีปุ่มกลับข้อความล่าสุด Action footer ต้องไม่บังเนื้อหาหรือหลุดกรอบเมื่อ iframe เตี้ย มี loading/empty/reconnect/error states และ keyboard focus ครบ

ชื่อ Faster-Whisper + Typhoon แสดงเป็นข้อมูลระบบได้ แต่คำว่า Live Syncing ต้องอิง event/health จริง ห้ามใช้ไฟเขียวค้างเพื่ออ้างว่าทั้ง AI และ WS พร้อม หากไม่มี confidence ให้แสดง “ยังไม่มีข้อมูล” ไม่ใส่ 96% สมมติ และไม่เรียก model confidence ว่า accuracy ที่วัดแล้ว

ภาพแนวคิดล่าสุด: `designs/05-multilingual-agent-copilot-clean-pro.png` เพิ่ม Dual Subtitles และ Tourist Assist จากภาพ 04 แล้ว ข้อมูลในภาพเป็นสาธิต ตัวภาพไม่ใช่ผลทดสอบ responsive หรือหลักฐานว่าระบบเชื่อมต่อแล้ว

## 4. Citizen Tracking Web คืออะไร

**Tracking เป็นเว็บ ส่วน SMS/LINE OA เป็นช่องทางส่งลิงก์** ทั้งสองช่องทางเปิดหน้าเว็บเดียวกันได้ โดยไม่ผูกฟังก์ชัน GPS/รูปกับแอป LINE

- หน้าเริ่มต้นแสดง Ticket ID, สรุปปัญหาสั้น, เวลาอัปเดต, เขต/หน่วยงานที่รับผิดชอบ
- Timeline 4 ขั้น: รับเรื่องแล้ว → ส่งสำนักงานเขตแล้ว → กำลังดำเนินการ → เสร็จสิ้น
- แสดงขั้นที่เกิดขึ้นจริงจาก Backend ไม่ทำ animation ข้ามสถานะตามเวลา หากส่งเขตล้มเหลวให้คงขั้นรับเรื่องแล้วพร้อมคำอธิบาย
- ปุ่มปักหมุดจุดเกิดเหตุ: ขอพิกัดเมื่อผู้ใช้กด, แสดง accuracy/ให้ตรวจและขยับจุดหรือกรอกสถานที่ได้ เพราะตำแหน่งมือถือปัจจุบันอาจไม่ใช่จุดเกิดเหตุ
- ปุ่มแนบรูป: preview, จำนวน/ขนาดตามสัญญาที่ตกลง, progress, retry, เก็บกับคำร้องเดิม ไม่ต้องใช้ MMS
- URL ต้องเปิดจากมือถือได้จริงผ่าน HTTPS; `localhost:8000` บนมือถือคือมือถือเอง ไม่ใช่เครื่อง Backend ของทีม ต้องจัด public/demo endpoint ที่เหมาะสมหรือเครือข่ายทดสอบที่เข้าถึงได้
- เบอร์ที่รับ SMS ได้แต่ไม่มี browser/internet ยังอ่านข้อความเลขเรื่องและสถานะสั้นได้ โดยสอบถามต่อด้วยเสียง การรับ SMS กว้างกว่าการใช้หน้า Tracking/GPS/รูป ซึ่งยังต้องใช้สมาร์ทโฟนและอินเทอร์เน็ต
- ลิงก์อ่าน/เพิ่มหลักฐานใช้ token ที่เดายากและกำหนดอายุ ไม่ใช้ Ticket ID ที่เรียงลำดับเป็นสิทธิ์เปิดข้อมูลทั้งหมด แยกสิทธิ์ดูสถานะจากสิทธิ์เพิ่ม/แก้หลักฐาน

## 5. SMS เทียบ LINE OA: ข้อเสนอเลือกใช้

**แนะนำ SMS เป็นช่องทางหลักของบริการประชาชน และ LINE OA เป็นตัวเลือกเสริมที่ผู้ใช้เลือกเอง** เหตุผลคือผู้โทรอาจไม่ใช้ LINE หรือไม่พร้อมเพิ่มเพื่อน ส่วนการทดสอบฟรีซ้ำหลายรอบ LINE OA เหมาะกว่าเมื่อทีมตั้งค่าบัญชีแล้ว การเลือกนี้เป็นข้อเสนอด้าน product ไม่ใช่การรับประกันคะแนน

| ประเด็น | SMS | LINE OA + Messaging API |
|---|---|---|
| การเริ่มต้นสำหรับผู้โทร | ใช้เบอร์มือถือที่ยืนยันได้ ไม่ต้องเพิ่มเพื่อน | ต้องมี LINE/internet และมี userId/สิทธิ์ส่งข้อความที่เหมาะสม |
| ผู้สูงอายุ/มือถือพื้นฐาน | รับข้อความสั้นได้บนมือถือที่รองรับ SMS | ใช้กับผู้ที่มีแอป/บัญชี LINE |
| รับข้อความเมื่อไม่ได้เปิดแอป | ไม่ต้องเปิด LINE แต่ยังมีเหตุส่งไม่ถึงได้ | แอปรับแจ้งเตือนเบื้องหลังได้ตามการตั้งค่า ไม่จำเป็นต้องเปิดแอปค้าง แต่ปิดแจ้งเตือน/บล็อก OA ได้ |
| ข้อมูลที่พาไป Tracking | เลขเรื่อง + ข้อความสั้น + ลิงก์ที่ provider อนุมัติ | Text/Flex Message พร้อมปุ่มเปิด Tracking เดิม |
| การทดสอบแบบฟรี | มีเครดิตฟรีทดลองจำกัดตามผู้ให้บริการ/การอนุมัติ | แพ็กเกจฟรีไทย 300 ข้อความ/เดือน เหมาะกับทีมเดโม |
| ต้นทุนระยะยาว | คิดต่อ segment/ผู้รับ ต้องมี budget | โควตารายเดือน; ข้อความ push นับโควตา |
| ข้อจำกัดก่อนเดโม | บัญชี, sender, credit, domain/link และมือถือปลายทาง | OA, Messaging API, secret/token, userId, การผูกกับคำร้อง |
| สิ่งที่ไม่ควรสมมติ | รับประกันส่งถึง หรือทดลองใช้ฟรีไม่จำกัด | นำ Caller ANI ไป push หา LINE user ได้โดยตรง |

### ข้อมูลปัจจุบันที่ตรวจจากแหล่งทางการ

- **LINE OA ประเทศไทย:** Free 300 ข้อความ/เดือนตาม [S1] โดย push/multicast/broadcast/narrowcast นับโควตา และ reply ไม่คิดในโควตานี้ตาม [S2] ดังนั้น scheduled status update ต้องใช้ push ไม่สามารถใช้ reply token เก่าส่งในอนาคตเพื่อหลีกเลี่ยงโควตา
- **LINE userId:** Messaging API ระบุผู้รับด้วย userId [S3] ต้องผูกคำร้องกับผู้ใช้ผ่าน session/รหัสยืนยันที่ Backend ตรวจ ไม่ใช่พิมพ์เลขคำร้องของใครก็รับแจ้งเตือนได้ ให้การรับ LINE เป็น opt-in และไม่บังคับประชาชนเพิ่มเพื่อนเพื่อรับบริการทางโทรศัพท์
- **ThaiBulkSMS:** FAQ ระบุทดลองฟรี 20 เครดิต แบ่ง Standard 10 และ Corporate 10 [S4] แต่ยังไม่ใช่หลักฐานว่าบัญชีของทีมได้รับเครดิตหรือส่ง tracking link ได้แล้ว ต้องทดลอง API/ข้อจำกัดของเครดิตแต่ละชนิดจริง
- **ความยาว SMS ไทย:** ผู้ให้บริการระบุ 70 ตัวอักษรต่อ 1 เครดิต และข้อความหลายส่วนมี overhead [S5] จึงไม่เท่ากับ 20 เรื่องเสมอไป คิดรวมข้อความไทย+เลขเรื่อง+URL ก่อนซ้อม
- **Sender/URL:** ต้องตรวจว่าชื่อผู้ส่งและโดเมน/ลิงก์ปลายทางผ่านเงื่อนไขผู้ให้บริการ โดยเฉพาะหน้าที่มี GPS/อัปโหลด เอกสาร Twilio สำหรับไทยระบุข้อจำกัด URL และหน้ารับข้อมูล [S6] อย่าเหมารวมว่าทุก provider อนุญาตเหมือนกัน; ถ้ายังไม่อนุมัติให้ทดสอบ SMS เลขเรื่อง/สถานะก่อน และใช้ QR/LINE แยกสำหรับหน้าเว็บอย่างเปิดเผย
- **Twilio trial:** เอกสาร trial ปัจจุบันระบุเส้นทาง SMS trial ส่งเฉพาะ verified US numbers และ template ที่กำหนด [S7] จึงไม่เลือกเป็นทางหลักสำหรับเดโมฟรีเข้าเบอร์ไทย ข้อมูล trial อาจต่างตามบัญชี ให้ยึดข้อจำกัดในบัญชีจริง
- **LINE Notify:** ยุติบริการแล้วตั้งแต่ 31 มีนาคม 2025 [S8] ถ้าทำ LINE ให้ใช้ OA Messaging API

ความเห็นผู้ใช้เรื่อง SMS เข้าถึงคนที่ไม่ใช้ LINE เหมาะกับโจทย์นี้ ส่วนคนที่ไม่ได้เปิด LINE ขณะนั้นอาจยังรับ push ได้เมื่อออนไลน์/เปิดแจ้งเตือน จึงควรแยก “ไม่มี LINE” จาก “ไม่ได้เปิดแอปตอนนี้”

## 6. แผนทดสอบโดยไม่เติมเงิน

### 6.1 ตั้งฐานซ้อมฟรีก่อน

ทำ notification adapter ฝั่ง Backend: `mock`, `sms`, `line` โดยตั้ง `mock` เป็นค่าเริ่มต้นใน simulator/mock เก็บข้อความใน outbox พร้อมป้าย “จำลอง ไม่ได้ส่งจริง” ซ้อม API/UI/retry/เปลี่ยนสถานะได้โดยไม่เสียเครดิต ไม่ใช้ mock เป็นหลักฐานว่ามือถือได้รับข้อความ

### 6.2 LINE OA สำหรับการรับข้อความจริงแบบฟรี

1. ใช้ OA เดิมของทีมถ้ามี หรือจัดทำบัญชี Free และเปิด Messaging API; ไม่ต้องสมัคร paid chat package เพื่อให้บอต push
2. ทีมทดสอบเพิ่มเพื่อน OA และรับ userId ผ่าน webhook/ข้อมูล developer สำหรับบัญชีทดสอบ [S3] เก็บ mapping ของคำร้องทดสอบกับคนที่ยืนยันแล้ว
3. ส่งเฉพาะผู้รับใน allowlist ที่ยินยอม, ใช้ 2 ข้อความต่อรอบ เช่น รับเรื่อง + เสร็จสิ้น; 50 รอบ/ผู้รับหนึ่งราย = 100 push recipients อยู่ใน 300 หากไม่มีการใช้โควตาอื่นร่วม
4. ตรวจข้อความบนเครื่องจริงและเปิด Tracking; API สำเร็จเพียงอย่างเดียวไม่รับประกันว่าผู้รับเห็นหรืออ่าน
5. จำกัดตัวนับส่งฝั่งแอป ตรวจ quota จริงก่อนเดโม หยุดเมื่อใกล้หมด ไม่อัปเกรดแพ็กเกจอัตโนมัติ

### 6.3 SMS สำหรับพิสูจน์ความครอบคลุม

1. ตรวจบัญชี/เครดิตที่ทีมมีอยู่ก่อน หากไม่มีให้ตรวจสิทธิ์ทดลองใช้ฟรี ThaiBulkSMS โดยไม่เติมเงิน; ยังไม่สร้างบัญชีแทนในงานวางแผนนี้
2. ยืนยัน sender และความสามารถส่งไปเบอร์ไทยของทีม รวมถึงการอนุมัติ tracking link ที่มีการกรอกข้อมูล หากมีเงื่อนไขไม่พร้อมต้องบันทึกตามจริง
3. ทดสอบกับเครื่องจริงของทีม 1–2 เครื่อง ใช้ข้อความสั้นและไม่มี emoji ตั้งงบเดโมในแอป 10 credits/วันที่ทดสอบก่อน และหยุดเมื่อเหลือไม่พอ ไม่ส่งถึงเบอร์นอก allowlist
4. ตรวจทั้ง API response, delivery report ที่ผู้ให้บริการมี และข้อความในเครื่องจริง จดเวลาส่ง/ถึง/เปิดแยกกัน
5. ถ้าฟรี trial ใช้ link ไม่ได้ ให้สาธิต SMS เลขเรื่องจริง และเปิดเว็บผ่าน QR/LINE แยกพร้อมบอกกรรมการตรงๆ ไม่ทำเป็นว่า SMS ส่ง link สำเร็จ

**ข้อสรุปเรื่องฟรี:** ซ้อมได้ฟรีแน่นอนใน mock mode; LINE OA ส่งข้อความจริงได้โดยไม่มีค่าข้อความเมื่อเข้าเงื่อนไข Free plan และเหลือโควตา; SMS ทดลองจริงอาจไม่ต้องจ่ายภายในเครดิต/เงื่อนไขที่อนุมัติ แต่ไม่สามารถรับประกันส่งจริงฟรีไม่จำกัด ทั้งสองแบบยังอาจมีต้นทุนอินเทอร์เน็ต/hosting ของระบบ

## 7. สัญญาข้อมูลที่ต้องเพิ่มจากโค้ดปัจจุบัน

โค้ดที่ตรวจยังมี `live_update` แบบ transcript ก้อนเดียว, หมวด/เขตตัวอย่างจำกัด, urgency low/medium/high, ปุ่ม dispatch เป็น alert และ in-memory tickets จึงยังทำตามบรีฟใหม่ทั้งหมดไม่ได้ ต้องตกลง Backend contract ก่อนเชื่อมจริง:

| ส่วน | ฟิลด์/พฤติกรรมเสนอ | ผู้รับผิดชอบ |
|---|---|---|
| Transcript | `segment_id`, `speaker`, `text`, `is_final`, `occurred_at`, entity spans | Watchara/Peerapun ส่ง speaker จาก audio channel/diarization ที่ตรวจได้ ไม่เดาจากข้อความ |
| Insight | `summary_points[3]`, category code จาก catalog 21 หมวด, district จาก 50 เขต, urgency, SLA, optional confidence | Peerapun; UI แสดงไม่ทราบเมื่อข้อมูลไม่มี ไม่สร้าง CRITICAL จาก high โดยพลการ |
| Context | conversationId จาก Genesys → interaction_id ของ Backend; session switching และ auth | Watchara + Aitthiphon |
| Save & dispatch | reserve draft หรือ create ครั้งเดียว + dispatch แบบ idempotent พร้อมรับรองผล | Peerapun; webhook ปัจจุบันสร้าง ticket แล้ว ต้องไม่สร้างซ้ำเมื่อกด |
| SMS/LINE notification | reference/draft id, recipient verified, purpose, channel, idempotency, provider receipt, queued/sent/delivered/failed | Backend ส่งผ่าน adapter; secret ไม่อยู่ใน iframe/Tracking JS |
| Tracking | status history 4 ขั้น, public token, read view และ write evidence แยกสิทธิ์ | Peerapun + Aitthiphon |
| GPS/รูป | coordinates + accuracy + observed_at + user confirmation; attachment metadata และการอ่านใหม่จาก Copilot | Peerapun + Aitthiphon |
| Duplicate | ระยะตัวอย่าง 100m, ย้อนหลัง 24h, category/issue similarity และรายการอ้างอิง | Peerapun; ไม่มีพิกัดให้แสดง “ยังตรวจระยะไม่ได้” |
| Persistence | ticket/history/outbox ไม่หายเมื่อ restart สำหรับช่วงซ้อม | Backend เลือกวิธีจัดเก็บตามข้อกำหนดทีม |

คำว่า “ส่งสำนักงานเขตแล้ว” ใช้เมื่อระบบส่งต่อยืนยันตามระดับการเชื่อมต่อจริง หากเป็น district adapter จำลองต้องติดป้าย การบันทึกคำร้องสำเร็จไม่เท่ากับเขตรับเรื่องแล้ว และส่ง notification ล้มเหลวไม่ควรทำให้สร้าง/dispatch คำร้องซ้ำ

บรีฟใช้ Faster-Whisper ที่ 5001 และ Typhoon ที่ 8001 ผ่าน DGX ตามข้อมูลจากทีม ให้ Browser เรียก middleware ที่ 8000 ไม่เรียก AI port โดยตรง ความเร็ว <200ms/ชื่อโมเดล/ความสามารถ streaming เป็นเป้าหมายหรือข้อมูลทีมจนกว่าจะวัดจริง แยก ASR latency, AI latency และ WS-to-render

เอกสาร FR3.2 เดิมกำหนดไม่เก็บเบอร์หลังส่ง SMS จึงต้องตกลง retention/contact store แยกก่อนทำ SMS แจ้งเตือนหลายวัน ไม่แอบเพิ่มเบอร์ลง ticket ถาวรเพื่อทำฟีเจอร์นี้

## 8. ลำดับงานเพิ่มเติมถึง 27 พฤศจิกายน

| วัน | งาน/ผลส่งมอบ |
|---|---|
| 23 พ.ย. | ยืนยัน iframe-first และ theme; ตรวจบัญชี SMS/OA, sender/link; ส่งข้อเสนอ contract ให้ทีมพิจารณาโดยยังไม่ส่งข้อความหาใคร |
| 24 พ.ย. | Agent iframe 400/450/500px + safe rendering + mock transcript สองฝั่ง + 3-point insight |
| 25 พ.ย. | ต่อ WS เปลี่ยนสายได้/reconnect; save & dispatch ack; ขอ GPS link ผ่าน notification adapter |
| 26 พ.ย. | Tracking 4 ขั้น, GPS/รูป, outbox/mock tests; LINE real test ภายในโควตา, SMS real test หากเครดิต/approval พร้อม |
| 27 พ.ย. | ส่ง prototype ตามบรีฟล่าสุด; ทดสอบต้นทางถึงปลายทางจริงและชุด fault; เตรียม screenshot/video backup |
| 28–29 พ.ย. | ซ้อมทีมและเก็บ latency/จำนวนส่งจริง; ปิด blocker ก่อนแข่ง |
| 30 พ.ย. | Smoke test กับเบอร์ทดสอบและมือถือปลายทาง, ตรวจ quota, demo ด้วยข้อมูลสมมติ |

เกณฑ์ตรวจ: สองสายไม่สลับข้อมูล, partial/final ไม่ซ้ำ, HTML ใน transcript ไม่ execute, reconnect ไม่ทำให้หน้าค้าง, dispatch ซ้ำไม่สร้าง ticket ซ้ำ, SMS fail ไม่แสดง delivered, ข้อมูล GPS/รูปกลับคำร้องถูกใบ, token หมดอายุ/ผิดใบปฏิเสธ, duplicate ไม่มีพิกัดไม่ให้ผลลวง, ไทม์ไลน์ไม่ข้ามขั้นเอง และชัดเจนว่า event/ข้อความใดเป็น mock

ตรวจ health ใน session นี้ที่ `http://127.0.0.1:8000/` ไม่สามารถเชื่อมต่อได้ ณ เวลาตรวจ จึงไม่อ้างว่าทดสอบ integration ผ่านแล้วหรือว่า service ที่อื่นของทีมล่ม ต้องรัน/เข้าถึง middleware ก่อนทดสอบขั้นต่อไป

## 9. แนวทางเพิ่มคุณค่าตามเกณฑ์คะแนน

อ้างอิง `docs/competition-details.md` §4: Functionality 30%, AI depth 25%, problem fit 20%, pitch/viability 15%, UX 10% เป็นเกณฑ์ในเอกสารทีม ยังไม่ใช่การยืนยันจากผู้จัดฉบับใหม่

แผนที่เสนอเน้น: โทรทดสอบจริง → แยกผู้พูด → AI สรุป/แนะนำเขต → เจ้าหน้าที่ตรวจและส่ง 1 คลิก → SMS เข้าเครื่องจริง → เปิด Tracking → ส่ง GPS/รูปกลับคำร้องเดิม ดีกว่าการเพิ่มหลายช่องทางแต่ยังไม่ครบเส้นทาง ส่วน LINE นำเสนอเป็นตัวเลือกสมัครใจในการติดตามต่อเนื่อง ไม่ทำเป็นเงื่อนไขรับบริการ

SMS ไม่มีคะแนนพิเศษอัตโนมัติ สิ่งที่นำไปอธิบายได้คือการเข้าถึงผู้ไม่ใช้ LINE, ลดการถามสถานที่ซ้ำ และพิสูจน์วงจรติดตามเรื่องครบ ส่วน AI summary/NER/duplicate ต้องใช้ข้อมูลจริงในการสาธิตหรือป้าย mock ไม่ตั้ง KPI ลด AHT เป็นผลวัดก่อนมีหลักฐาน

## 10. แหล่งอ้างอิงที่ตรวจ

- [B1 — บรีฟล่าสุดของทีมบน GitHub](https://github.com/winnawat2023/BKK-CivicVoice-AI/blob/main/docs/design-brief-aitthiphon.md) connector ระบุ modified 2026-11-23T11:54:15Z; ไฟล์นี้ยังไม่มีใน local checkout ณ เวลาตรวจ ไม่ได้ pull/merge ทับงานในเครื่อง
- อัปเดต 23 พ.ย. 2026 ตามบรีฟ Tourist Assist: นำฉบับล่าสุดที่อ่านจาก GitHub มาไว้ใน `docs/design-brief-aitthiphon.md` แล้วโดยไม่ pull/merge งานอื่น และเพิ่มแผน `tourist-assist-plan.md`
- [S1 — LINE OA Thailand: packages](https://lineforbusiness.com/th/service/line-oa-features/broadcast-message)
- [S2 — LINE Messaging API pricing/counting](https://developers.line.biz/en/docs/messaging-api/pricing/)
- [S3 — LINE: Get user IDs](https://developers.line.biz/en/docs/messaging-api/getting-user-ids/)
- [S4 — ThaiBulkSMS FAQ: trial credits](https://www.thaibulksms.com/faq/)
- [S5 — ThaiBulkSMS credit calculation](https://www.thaibulksms.com/credit-calculation/)
- [S6 — Twilio Thailand SMS guidelines](https://www.twilio.com/en-us/guidelines/th/sms)
- [S7 — Twilio SMS trial restrictions](https://www.twilio.com/docs/usage/trials/try-out-sms)
- [S8 — LINE Notify end-of-life](https://developers.line.biz/en/news/2024/?article=line-notify-will-be-discontinued&day=07&month=10)

ภาพแนวคิดสร้างด้วย built-in image_gen; prompt ฉบับเต็มอยู่ใน `generation-prompts-v2.json` งานครั้งนี้เป็นการวางแผนและทำภาพ ยังไม่ได้แก้โค้ดแอป เปิดบัญชีใหม่ ใช้เครดิต ส่ง SMS/LINE โทรออก หรือเผยแพร่ระบบ
