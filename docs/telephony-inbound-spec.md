# 📞 Genesys Cloud Inbound Telephony Specification
**โครงการ:** BKK CivicVoice AI (AI Skill Wars 2026 : AI For Bangkok)  
**องค์กร Genesys Cloud:** `ark-insights`  
**อัปเดตล่าสุด:** 23 พฤศจิกายน 2569

---

## 1. ข้อมูลเบอร์โทรศัพท์สำหรับการทดสอบและประกวด (Phone Number)

| รายการ | รายละเอียด |
|---|---|
| **เบอร์โทรศัพท์ Inbound (Test DID):** | **`02-096-6763`** (หรือ `+66-2-096-6763`) |
| **ประเภทคู่สาย:** | Direct Inward Dialing (DID) / SIP Trunk |
| **บทบาทในระบบ:** | ใช้จำลองเป็นเบอร์สายด่วน กทม. 1555 สำหรับการทดสอบ (Testing) และการสาธิตสดบนเวที (Live Demo) |
| **Genesys Organization:** | `ark-insights` |
| **ผู้รับผิดชอบหลัก:** | คุณวัชระ บังเกิดลาภ (Genesys Cloud CX Specialist) |

---

## 2. การตั้งค่าบน Genesys Cloud CX Architect (Configuration Matrix)

### 2.1 DID / Phone Number Mapping:
- **Number:** `+6620966763` / `020966763`
- **Routing:** Direct to Architect Inbound Call Flow: `BKK_CivicVoice_1555_Flow`

### 2.2 Architect Inbound Call Flow Sequence:
1. **Initial Greeting:** 
   - เล่นเสียงตอบรับ: *"ยินดีต้อนรับสู่ศูนย์รับเรื่องร้องทุกข์สายด่วน กทม. 1555 ระบบอัจฉริยะ BKK CivicVoice AI กำลังเชื่อมต่อสายเข้าสู่เจ้าหน้าที่..."*
2. **Audio Streaming & Webhook Trigger:**
   - ส่ง HTTP POST ไปยัง CivicVoice API Gateway:
     - **Webhook URL:** `https://voiceai-demo.ark-insights.com/api/v1/genesys/webhook`
     - **DNIS (Dialed Number):** `02-096-6763`
     - **ANI (Caller ID):** เบอร์ผู้โทรเข้า
     - **Interaction ID:** Genesys Conversation ID
3. **Queue & Screen Pop:**
   - Route สายไปยัง Queue: `BKK_1555_General_Queue`
   - Agent Desktop ทำการ Screen Pop เปิด Iframe Widget:
     - **Widget URL:** `https://voiceai-demo.ark-insights.com/widget/index.html?interactionId={{Conversation.Id}}&ani={{Call.Ani}}`

---

## 3. Checklist การทดสอบสายโทรจริง (Live Testing Checklist):
- [ ] โทรจากเบอร์มือถือภายนอก (AIS / True / Dtac) เข้าเบอร์ **`02-096-6763`** ติดสมบูรณ์
- [ ] เสียง IVR ภาษาไทยชัดเจน ไม่กระตุก
- [ ] สายวิ่งเข้า Queue ใน Genesys Cloud Agent Desktop ของผู้เข้าแข่งขัน
- [ ] Agent Desktop ป๊อปอัปหน้าต่าง Copilot Widget อัตโนมัติ
- [ ] สัญญาณเสียงถอดเทปภาษาไทยเรียลไทม์บน Widget ภายในเวลา < 200ms
