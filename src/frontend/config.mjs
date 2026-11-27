export const deployment = {
  apiBase: "",
  asrBase: "",
  smsBase: "",
  allowInternalTracking: false,
  enableSocketCreate: false,
  // Point apiBase at an authenticated gateway before enabling voice on a public host.
  enableCitizenVoice: false,
};

export function settings(search = location.search, origin = location.origin) {
  const params = new URLSearchParams(search);
  const demo = params.get("mode") === "demo";
  const customBase = params.get("apiBase");
  const page = new URL(origin);
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(page.hostname);
  const api = new URL((local && customBase) || deployment.apiBase ||
    (local && new URL(origin).port === "8765" ? "http://127.0.0.1:8000" : origin));
  if (!["http:", "https:"].includes(api.protocol) || api.username || api.password ||
      (new URL(origin).protocol === "https:" && api.protocol !== "https:")) {
    throw new Error("ต้องใช้ API origin แบบ HTTP/HTTPS ที่เข้ากับหน้าปัจจุบัน");
  }
  return {
    apiBase: api.origin,
    asrBase: deployment.asrBase || (local && page.port === "8765" ? "http://127.0.0.1:5001" : origin),
    smsBase: deployment.smsBase || (local && page.port === "8765" ? page.protocol + "//" + page.hostname + ":8766" : origin),
    demo,
    local,
    citizenLive: local || deployment.enableCitizenVoice,
    internal: params.get("mode") === "internal" && (local || deployment.allowInternalTracking),
    interaction: (params.get("interaction_id") || params.get("conversationId") || params.get("conversationid") || "").trim(),
    ticketId: (params.get("ticket") || "").trim(),
    enableSocketCreate: local || deployment.enableSocketCreate,
  };
}
