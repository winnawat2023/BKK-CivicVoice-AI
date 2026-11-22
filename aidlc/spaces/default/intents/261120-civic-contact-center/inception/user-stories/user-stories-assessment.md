# User Stories Assessment: BKK CivicConnect AI

อ้างอิง: `requirements.md` (Requirements Analysis) และ `team-practices.md` (Practices Discovery)

## Decision

**Execute**

## Rationale

ระบบมีผู้ใช้ 3 กลุ่มที่ใช้งานต่างกัน คือประชาชนที่โทรเข้า เจ้าหน้าที่ศูนย์ 1555 และเจ้าหน้าที่สำนักงานเขต และมีฟีเจอร์ที่ผู้ใช้เห็นโดยตรง ได้แก่ การรับสายและแจ้งปัญหา หน้าตรวจสอบสถานะ และหน้าจอเจ้าหน้าที่ เรื่องราวผู้ใช้ช่วยให้เกณฑ์ผ่านของแต่ละเส้นทางตรวจได้ [requirements.md]

## Factors considered

- ประเภทโปรเจกต์: โปรเจกต์ใหม่ (greenfield) ขอบเขต mvp
- ขอบเขตที่ผู้ใช้เห็น: เสียงทางโทรศัพท์ หน้าเว็บบนมือถือ และ Widget ใน Genesys Agent Workspace
- ความซับซ้อน: มีหลายเส้นทางการใช้งานและมีกรณีผิดพลาด (ฟังไม่เข้าใจ ไม่พบ Ticket ไม่มี Caller ID)

## Key areas where stories add the most value

- เส้นทางแจ้งปัญหาตั้งแต่โทรเข้าจนได้ Ticket ID (US1.1, US1.2, US1.4) ซึ่งเป็นชิ้นงานบางๆ ที่ต้องทำก่อนตามวิธีทำงานของทีม [team-practices.md]
- เกณฑ์ผ่านของการสาธิตขั้นต่ำใน `scope-document.md`

## Assumptions & Open Questions

- ไม่ได้ใช้ผู้ร่วมงาน (นักออกแบบ นักพัฒนา ทีมทดสอบ) เพราะตั้งค่าปิดไว้ในโปรเจกต์นี้ ผู้นำฝ่ายผลิตภัณฑ์จะเป็นผู้ตรวจภายหลัง [assumption]
