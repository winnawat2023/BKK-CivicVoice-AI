export const demoInteraction = "CALL-9042-DEMO";
export const demoTicket = {
  ticket_id: "BKK-2026-0001",
  interaction_id: demoInteraction,
  category: "อื่นๆ",
  sub_category: "ท่อระบายน้ำ/น้ำท่วม",
  district: "คลองเตย",
  location_detail: "ซอยสุขุมวิท 50",
  urgency: "high",
  summary_lines: ["ฝาท่อชำรุด เสี่ยงอุบัติเหตุ", "ซอยสุขุมวิท 50 เขตคลองเตย", "ประสานฝ่ายโยธาตรวจสอบ"],
  target_unit: "ฝ่ายโยธา สำนักงานเขต",
  sla_days: 3,
  status: "รับเรื่องแล้ว",
  dispatched: false,
  created_at: "2026-11-25T10:24:00",
};
export const demoSegments = [
  { seq: 1, speaker: "caller", text: "There is a broken manhole cover on Sukhumvit 50.",
    source_language: "en", translated_text: "ฝาท่อชำรุดที่ซอยสุขุมวิท 50", ts: "2026-11-25T10:24:00" },
  { seq: 2, speaker: "agent", text: "รับทราบค่ะ ขอพิกัดจุดเกิดเหตุเพิ่มเติมนะคะ", ts: "2026-11-25T10:25:00" },
];
export const demoScript = {
  english_text: "Could you share your location, please?",
  thai_meaning: "กรุณาส่งพิกัดจุดเกิดเหตุ",
  thai_pronunciation: "คูด ยู แชร์ ยัวร์ โลเคชัน พลีซ",
};

const thaiInteraction = "CALL-9043-DEMO";
export const demoCases = [
  {
    key: "tourist", name: "ฝาท่อชำรุด · สุขุมวิท 50", language: "EN → TH",
    ani: "08x-xxx-1234", ticket: demoTicket, segments: demoSegments, script: demoScript,
    duplicate: true,
    nextSegment: {
      seq: 3, speaker: "caller", source_language: "en", ts: "2026-11-25T10:26:00",
      text: "It is near the entrance to Sukhumvit 50, next to the bus stop.",
      translated_text: "อยู่ใกล้ปากซอยสุขุมวิท 50 ข้างป้ายรถเมล์",
    },
  },
  {
    key: "lighting", name: "ไฟถนนดับ · ซอยลาดพร้าว 101", language: "TH",
    ani: "09x-xxx-2480",
    ticket: {
      ticket_id: "BKK-2026-0002", interaction_id: thaiInteraction, district: "บางกะปิ",
      location_detail: "ซอยลาดพร้าว 101", category: "ไฟฟ้า", urgency: "medium",
      summary_lines: ["ไฟถนนดับสองดวง", "ซอยลาดพร้าว 101 เขตบางกะปิ", "ประสานตรวจระบบไฟส่องสว่าง"],
      status: "รับเรื่องแล้ว", dispatched: false,
    },
    segments: [
      { seq: 1, speaker: "caller", text: "ไฟถนนดับสองดวงตรงซอยลาดพร้าว 101 ค่ะ", ts: "2026-11-25T10:29:00" },
      { seq: 2, speaker: "agent", text: "ขอจุดสังเกตใกล้เคียงด้วยค่ะ", ts: "2026-11-25T10:30:00" },
    ],
    nextSegment: {
      seq: 3, speaker: "caller", ts: "2026-11-25T10:31:00",
      text: "อยู่หน้าปากซอยลาดพร้าว 101 แยก 10 ค่ะ",
    },
  },
];

export const demoChannel = "bkk-civicvoice-agent-demo";
