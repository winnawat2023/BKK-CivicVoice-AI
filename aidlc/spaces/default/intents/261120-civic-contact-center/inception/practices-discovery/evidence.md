# Evidence

## สิ่งที่ตรวจสอบ

- Lead (aidlc-pipeline-deploy-agent): อ่านส่วน Way of Working, Walking Skeleton, Testing Posture, Deployment, Code Style ใน `aidlc/spaces/default/memory/org.md` เป็นค่าเริ่มต้นที่เสนอ
- `memory/team.md` และ `memory/project.md`: ว่าง ไม่มีแนวปฏิบัติที่ยืนยันแล้ว
- `scope-document.md`: scope mvp, ทีม 3 ถึง 4 คน, 1 วัน, สาธิตสด 30 พฤศจิกายน 2569, Genesys ต้องเสร็จก่อน
- โฟลเดอร์ทำงานไม่ใช่ git repository จึงไม่มีประวัติ commit, branch หรือ CI ให้อนุมาน
- ไม่มี collaborator (collaborators off) จึงไม่มีไฟล์ contribution

## สิ่งที่อนุมาน

- ร่างแรกเป็นข้อเสนอจาก org.md ไม่ใช่ข้อเท็จจริงของทีม ฉบับนี้ใช้คำตอบที่มนุษย์ยืนยันแล้วแทน

## การตัดสินใจจากการสัมภาษณ์

- Q1: แตก branch สั้นๆ ต่อฟีเจอร์ แล้วรวมกลับเข้า `main` ต้อง `git init` ก่อน
- Q2: ทำ walking skeleton ก่อน (Genesys, สร้าง Ticket, เห็น Ticket ID)
- Q3: TDD (เขียนเทสต์ก่อนโค้ด)
- Q4: เกณฑ์ coverage 80% ตามค่าเริ่มต้นของ mvp
- Q5: ระบบสาธิตรันบนเครื่องของทีมเอง ไม่มี production
- Q6: formatter และ linter มาตรฐานของภาษา ตั้งที่ root และตั้งชื่อตามแบบของภาษา
- Q7: ยังไม่กำหนดกฎแข็ง จึงไม่มีรายการ Mandated หรือ Forbidden
- มนุษย์ยืนยันสรุปรวมว่า "Looks correct"

## ความไม่แน่นอนที่ยังเหลือ

1. เกณฑ์ coverage 80% ภายในเวลา 1 วัน พร้อม TDD อาจกดดันเวลา ทีมอาจต้องทบทวนถ้าเวลาไม่พอ แต่ห้ามลดเกณฑ์ผ่านขั้นตอนนี้
2. Q7 ยังไม่กำหนด เช่น ยังไม่มีกฎ "ห้ามใช้ข้อมูลหรือเสียงจริงของประชาชน" เป็นกฎแข็ง
3. ภาษา, กรอบงาน, formatter และ linter ที่แน่ชัดยังไม่ถูกเลือก (เลือกในขั้นตอนออกแบบ)
4. ยังไม่มี git repository ต้อง `git init` ก่อนใช้ branch ตามที่ตกลง
