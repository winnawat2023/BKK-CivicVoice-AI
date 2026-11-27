export const statuses = ["รับเรื่องแล้ว", "กำลังดำเนินการ", "แก้ไขเสร็จ"];
export const timeline = [statuses[0], "ส่งสำนักงานเขตแล้ว", statuses[1], "เสร็จสิ้น"];

export function trackingStep(ticket) {
  if (ticket.status === statuses[2]) return 3;
  if (ticket.status === statuses[1]) return 2;
  if (ticket.dispatched === true || ticket.dispatched_at) return 1;
  return ticket.status === statuses[0] ? 0 : -1;
}

export function updateSegments(list, segment) {
  if (typeof segment?.text !== "string" || !["caller", "agent", "bot"].includes(segment.speaker)) return list;
  const row = { ...segment, is_final: segment.is_final !== false };
  const hasKey = value => value.segment_id != null || value.seq != null;
  const match = list.findIndex(old => old.speaker === row.speaker && (
    row.segment_id != null && old.segment_id === row.segment_id ||
    row.seq != null && old.seq === row.seq
  ));
  if (match >= 0) {
    const old = list[match];
    if ((old.is_final && !row.is_final) || (old.revision ?? 0) > (row.revision ?? 0)) return list;
    return list.map((entry, i) => i === match ? { ...entry, ...row } : entry);
  }
  const partial = list.findLastIndex(old => old.speaker === row.speaker && !old.is_final &&
    (old.segment_id == null || row.segment_id == null));
  if (partial >= 0) {
    if (hasKey(row) && Number.isFinite(row.seq) && row.seq < list[partial].seq) return list;
    return list.map((entry, i) => i === partial ? row : entry);
  }
  return [...list, row].slice(-100);
}

export function decodeEvent(raw, interaction) {
  const packet = JSON.parse(raw);
  if (!packet || typeof packet.event !== "string") return null;
  const data = packet.data ?? packet;
  if (!data || typeof data !== "object") return null;
  const reported = [packet.interaction_id, data.interaction_id, data.ticket?.interaction_id,
    data.segment?.interaction_id, data.analysis?.interaction_id].filter(Boolean);
  return reported.some(id => id !== interaction) ? null : { event: packet.event, data };
}
