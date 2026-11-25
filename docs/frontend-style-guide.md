# Frontend Style Guide — Soft Blue

ใช้ธีม **02 Soft Blue** สำหรับหน้าเว็บประชาชน ป๊อปอัป BKK CivicVoice, Agent Copilot และ Citizen Tracking ขาว–ฟ้าเป็นพื้นหลัก น้ำเงินเข้มใช้กับปุ่มหลักและลิงก์ โลโก้ ARK Insights ใช้ในหัวป๊อปอัปและ Agent Copilot ดู [ภาพอ้างอิง Soft Blue](../aidlc/spaces/default/intents/261120-civic-contact-center/inception/refined-mockups/frontend-widget-proposal/designs/02-soft-blue.png)

## สีและตัวอักษร

| ส่วน | ค่าที่ใช้ในต้นแบบล่าสุด |
| --- | --- |
| พื้นและเส้นขอบ | พื้นหลัก `#EFF6FF`, การ์ด `#FFFFFF`, เส้นขอบ `#DBE5F1` |
| ข้อความ | Navy `#0F172A`, ข้อความรอง `#475569` |
| ปุ่มหลัก | น้ำเงิน `#184AD4` และไล่สี `#286AF2` → `#114BD6` บนปุ่มของป๊อปอัป ข้อความสีขาว |
| สถานะ | เขียว `#10B981` สำหรับสถานะพร้อมหรือสำเร็จ ฟ้า `#06B6D4` สำหรับองค์ประกอบ AI และสีม่วงสำหรับไอคอนสรุป |
| ข้อผิดพลาดและเร่งด่วน | สีแดง `#991B1B` สำหรับข้อความผิดพลาดหรือระดับวิกฤต และสีอำพัน `#92400E` สำหรับระดับสูง |
| ฟอนต์ | Sarabun ที่เสิร์ฟจากไฟล์ในโปรเจกต์ น้ำหนัก 400, 600 และ 700 ขนาดพื้นฐาน 16px ระยะบรรทัด 1.5 |

## การจัดวางและปุ่ม

| หน้าจอ | การจัดวางและพฤติกรรม |
| --- | --- |
| เว็บประชาชนและป๊อปอัป | หน้าเว็บตัวอย่างใช้ภาพเส้นขอบฟ้ากรุงเทพฯ และการ์ดบริการ ปุ่ม **ติดต่อเรา** อยู่มุมขวาล่าง พื้นน้ำเงินคงเดิมเมื่อ hover และเพิ่มเงาฟ้า ป๊อปอัปกว้างสูงสุด 400px มีขอบโค้ง 20px และเลื่อนเฉพาะในกรอบเมื่อพื้นที่แนวตั้งจำกัด |
| สรุปเรื่องของประชาชน | กด **จบและดูสรุป** เพื่อแสดงการ์ด **สรุปโดย AI** รายการสรุป ป้ายหมวดหมู่ และการ์ดสำนักงานเขต ทั้งสองหน้าจอใช้รูปแบบการ์ดสรุปร่วมกัน ปุ่มหลักฝั่งประชาชนคือ **ยืนยันแจ้งปัญหา** ส่วนปุ่มขอ SMS จะปรากฏเมื่อได้เลขคำร้องแล้ว |
| Agent Copilot | Iframe คอลัมน์เดียวสำหรับเจ้าหน้าที่ 400–500px หัวหน้าจอแสดง `ark-insights` สถานะการเชื่อมต่อ Interaction ID และเบอร์สายเรียกเข้าตามข้อมูลของสายนั้น กล่อง Transcript แยกสีตามผู้พูดและไฮไลต์สถานที่ ใต้สรุปมี Tourist Assist เมื่อมีข้อมูล และปุ่มหลัก **บันทึกคำร้องและส่งสำนักงานเขต** |
| Citizen Tracking | หน้าเว็บมือถือแสดงเลขคำร้องและ Timeline 4 ขั้นในเดโม ลิงก์ส่งหลักฐานเปิดหน้าเพิ่มข้อมูลของคำร้องนั้นโดยตรง ให้ผู้ใช้ตรวจพิกัดปัจจุบันหรือดูตัวอย่างรูปก่อนกดยืนยันส่ง |

ทดสอบการอ่านที่ความกว้าง 390px บนมือถือและ 400/450/500px ใน iframe ตรวจขอบโฟกัสที่เห็นชัดด้วยคีย์บอร์ด แสดงสถานะด้วยข้อความควบคู่สี และปิด transition ของปุ่มในป๊อปอัปเมื่อผู้ใช้ตั้งค่า `prefers-reduced-motion` ข้อความตอบกลับของ SMS ต้องระบุว่าเป็นลิงก์จำลองหรือผู้ให้บริการรับคำขอแล้วตามผลจริง

HTML5, Tailwind CSS ที่คอมไพล์ไว้ และ Vanilla JS ใช้ `src/frontend/styles.css` สำหรับสไตล์ร่วม `citizen.css` สำหรับป๊อปอัป `widget/soft-blue.css` สำหรับ iframe และ `summary.css` คู่กับ `summary.mjs` สำหรับการ์ดสรุปทั้งสองฝั่ง วิธีรันและตั้งค่าอยู่ใน [README](../README.md#3-เปิดหน้าจอ-genesys-agent-widget)

## ภาพจากต้นแบบ

- [หน้าประชาชนหลังยืนยันคำร้องและเปิดฟอร์ม SMS](../aidlc/spaces/default/intents/261120-civic-contact-center/inception/refined-mockups/frontend-widget-proposal/designs/09-citizen-sms-browser-demo.png)
- [Agent Copilot ขนาด 450px](../aidlc/spaces/default/intents/261120-civic-contact-center/inception/refined-mockups/frontend-widget-proposal/designs/07-agent-copilot-browser-demo.png)
- [Citizen Tracking ขนาด 390px](../aidlc/spaces/default/intents/261120-civic-contact-center/inception/refined-mockups/frontend-widget-proposal/designs/08-citizen-tracking-browser-demo.png)
