# Unit-to-Story Map: BKK CivicConnect AI

อ้างอิง: `components.md` (Domain Design), `requirements.md`, `stories.md` (User Stories), `unit-of-work.md` และ `unit-of-work-dependency.md` แถวละหนึ่งเรื่องราวผู้ใช้ ระบุ Unit ที่สร้างเรื่องนั้น Unit ที่ระบุในแถวต้องสร้างและทดสอบเกณฑ์ผ่านทั้งหมดของเรื่องนั้นใน Functional Design จึงระบุ Unit เฉพาะที่สร้างส่วนหนึ่งของเรื่องนั้นจริง

## การจับคู่เรื่องราวกับ Unit

| Story | Unit ID | Directory |
|---|---|---|
| US1.1 | U1 | u1-call-to-ticket |
| US1.2 | U1 | u1-call-to-ticket |
| US1.3 | U2 | u2-ask-back-and-transfer |
| US1.4 | U3 | u3-notifications |
| US1.5 | U4 | u4-citizen-status |
| US1.6 | U6 | u6-knowledge-answers |
| US1.7 | U2 | u2-ask-back-and-transfer |
| US1.8 | U3 | u3-notifications |
| US2.1 | U5 | u5-staff-tickets |
| US2.2 | U5 | u5-staff-tickets |
| US2.3 | U7 | u7-agent-widget |
| US2.4 | U7 | u7-agent-widget |
| US2.5 | U5; U7 | u5-staff-tickets; u7-agent-widget |
| US3.1 | U5 | u5-staff-tickets |

## เรื่องที่ข้ามหลาย Unit

- **US2.5 (ส่งต่อให้สำนักงานเขต):** U5 สร้างความสามารถทำเครื่องหมายส่งต่อ (เกณฑ์ AC2.5.1 ส่วน Ticket ถูกทำเครื่องหมาย) และ U7 สร้างปุ่มใน Widget ที่เรียกความสามารถนั้น
- **ข้อกำหนดที่ใช้ร่วม (NFR1 ถึง NFR6):** ไม่อยู่ในตารางนี้ เพราะตารางนี้ระบุเฉพาะเรื่องราวผู้ใช้ NFR ที่ผู้ใช้เห็น ถูกตามรอยผ่านเรื่องราวที่เกี่ยวข้องแล้วใน User Stories

## ลำดับการสร้างภายในแต่ละ Unit

ลำดับภายใน Unit เป็นเรื่องของ Unit นั้นเอง ไม่ใช่ลำดับของทั้งโครงการ ซึ่งตัดสินใน Delivery Planning

- **U1:** สายเข้าและแยกประเภท (US1.1) ก่อน แล้วสกัดข้อมูลและสร้าง Ticket (US1.2) เพราะ US1.2 ต้องการสายที่แยกประเภทแล้ว
- **U2:** ถามกลับเรื่องสถานที่ (US1.3) แล้วถามซ้ำและโอนสาย (US1.7)
- **U3:** SMS (US1.4) ก่อน แล้ว LINE OA (US1.8) ซึ่งตัดได้
- **U5:** รายการและรายละเอียด (US2.1) ก่อน แล้วเปลี่ยนสถานะ (US2.2) แล้วส่งต่อและมุมมองของเขต (US2.5 ส่วนหลังบ้าน และ US3.1)
- **U7:** สรุปและข้อมูล Ticket (US2.3) ก่อน แล้วบทสนทนาสด (US2.4) แล้วปุ่มส่งต่อ (US2.5 ส่วนปุ่ม)

## การตรวจความครอบคลุม

- เรื่องราวผู้ใช้ทั้ง 14 เรื่อง (US1.1 ถึง US3.1) ถูกกำหนดให้ Unit ครบทุกเรื่อง
- ทุก Unit มีอย่างน้อยหนึ่งแถว: U1 (2), U2 (2), U3 (2), U4 (1), U5 (4), U6 (1), U7 (3)

## Assumptions & Open Questions

- เรื่อง US2.5 ใช้สอง Unit ตามที่ตกลงในแผนที่คุณอนุมัติ ถ้าตัด Widget (U7) ส่วนที่ทำเครื่องหมายส่งต่อใน U5 ยังใช้ได้จากหน้ารายการ แต่ยังไม่ได้กำหนดว่าหน้ารายการมีปุ่มส่งต่อหรือไม่ [assumption]
- ข้อกำหนด NFR4 (TDD และ coverage 80%) และ NFR5 (รันบนเครื่องของทีม) ใช้กับทุก Unit และตรวจในขั้นตอน Build and Test กับ Infrastructure Design [assumption]
