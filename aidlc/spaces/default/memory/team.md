# Team-Level Rules

> This team's affirmed practices and corrections. Loaded after `org.md` as
> strict-additive guidance.
> Populated by the practices-discovery affirmation gate. Edit at the gate,
> not directly.

## Way of Working

- **Integration branch**: main
- ทีมแตก branch สั้นๆ ต่อฟีเจอร์ แล้วรวมกลับเข้า `main` (Q1)
- โฟลเดอร์ทำงานยังไม่ใช่ git repository ทีมต้องรัน `git init` ก่อนเริ่มเขียนโค้ด เพื่อให้ใช้ branch และย้อนการแก้ไขได้

## Walking Skeleton

- ทีมสร้างชิ้นงานบางๆ ที่ทำงานครบตั้งแต่ต้นจนจบก่อน คือรับสายเข้าจาก Genesys, สร้าง Ticket และเห็น Ticket ID แล้วจึงเพิ่มฟีเจอร์อื่น (Q2)
- เหตุผล: การเชื่อม Genesys เป็นความเสี่ยงสูงสุดและต้องเสร็จก่อนทุกอย่าง

## Testing Posture

- **Methodology**: tdd
- **Methodology evidence**: ทีมเลือกเขียนการทดสอบก่อนโค้ดแบบ TDD ในการสัมภาษณ์ข้อ Q3 (ตัวเลือก B)
- **Ordering**: เขียนเทสต์ก่อนและรันให้เห็นว่าล้มเหลว แล้วจึงเขียนโค้ดให้ผ่านเทสต์นั้น
- ความครอบคลุมของบรรทัดโค้ดไม่ต่ำกว่า 80% และรันก่อน merge (Q4)
- เทสต์ชุดที่มีอยู่ต้องผ่านต่อเนื่องเสมอ (existing suite stays green)

## Guard Policy

<!-- Affirmed by the team. Mode: strict, relaxed, or off. Strict here holds for every intent, whatever one person asks in chat; relaxed or off here applies to every intent whose policy came from its scope, unless project.md or the person sets another; changing this line changes it. A section under the retired Change Control heading, written by an earlier release, is still read. -->

## Deployment

- ระบบสาธิตรันบนเครื่องของทีมเองตลอดช่วงสาธิต (Q5)
- ไม่มีระบบ production จริง และไม่ใช้ AWS

## Code Style

- ใช้ formatter และ linter มาตรฐานของภาษาที่เลือก ตั้งค่าไว้ที่ root ของโปรเจกต์ (Q6)
- ตั้งชื่อตามแบบของภาษานั้น (language-idiomatic)
- ภาษาและกรอบงานจะเลือกในขั้นตอนออกแบบ
## Forbidden

<!-- Team-specific forbidden patterns -->

## Mandated

<!-- Team-specific mandates -->

## Corrections

<!-- Self-learning loop appends here. -->
