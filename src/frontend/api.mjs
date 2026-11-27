export class MiddlewareError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export function middleware(base, request = fetch) {
  async function response(path, options = {}) {
    const result = await request(new URL(path, base), {
      cache: "no-store",
      signal: AbortSignal.timeout(25000),
      ...options,
    });
    if (!result.ok) {
      const { detail } = await result.json().catch(() => ({}));
      const message = typeof detail === "string" ? detail :
        Array.isArray(detail) ? detail.map(({ msg }) => msg).filter(Boolean).join("; ") : "";
      throw new MiddlewareError(message || `API ตอบกลับ HTTP ${result.status}`, result.status);
    }
    return result;
  }

  const ticketPath = id => `/api/v1/tickets/${encodeURIComponent(id)}`;
  const json = body => ({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const bearer = token => ({ Authorization: `Bearer ${token}` });
  const cancellable = signal => signal ? { signal: AbortSignal.any([signal, AbortSignal.timeout(25000)]) } : {};
  async function audio(path, signal) {
    const result = await response(path, cancellable(signal));
    if (!result.headers.get("Content-Type")?.startsWith("audio/")) {
      throw new Error("API ไม่ได้ส่งไฟล์เสียงกลับมา");
    }
    return result.blob();
  }
  return {
    health: async () => (await response("/api/v1/health?check_llm=false")).json(),
    transcribe: async (recording, signal) => {
      const form = new FormData();
      form.set("file", recording, recording.type.startsWith("audio/mp4") ? "voice.m4a" : "voice.webm");
      form.set("language", "th");
      form.set("forward", "false");
      return (await response("/v1/transcribe", {
        method: "POST", body: form, signal: AbortSignal.any([signal, AbortSignal.timeout(45000)]),
      })).json();
    },
    voiceTurn: async (body, signal) => (await response("/api/v1/voicebot/converse", {
      ...json(body), ...cancellable(signal),
    })).json(),
    smsHealth: async () => (await response("/api/sms/health", { signal: AbortSignal.timeout(1600) })).json(),
    confirmWithSms: async body => (await response("/api/sms/confirm", {
      ...json(body), signal: AbortSignal.timeout(45000),
    })).json(),
    sendEvidenceSms: async (grant, phone) => {
      const request = json({ phone });
      request.headers = { ...request.headers, ...bearer(grant) };
      return (await response("/api/sms/send", request)).json();
    },
    evidence: async token => (await response("/api/sms/evidence", { headers: bearer(token) })).json(),
    saveLocation: async (token, location) => {
      const request = json(location);
      request.method = "PUT";
      request.headers = { ...request.headers, ...bearer(token) };
      return (await response("/api/sms/evidence/location", request)).json();
    },
    saveMapLink: async (token, url) => {
      const request = json({ map_url: url });
      request.method = "PUT";
      request.headers = { ...request.headers, ...bearer(token) };
      return (await response("/api/sms/evidence/map-link", request)).json();
    },
    savePhoto: async (token, file) => (await response("/api/sms/evidence/photo", {
      method: "PUT", body: file, headers: { ...bearer(token), "Content-Type": file.type },
      signal: AbortSignal.timeout(90000),
    })).json(),
    classify: async text => (await response("/api/v1/civic/classify", json({ text }))).json(),
    districts: async () => (await response("/api/v1/civic/districts")).json(),
    voiceReplyAudio: (url, signal) => {
      const target = new URL(url, base);
      if (target.origin !== new URL(base).origin || target.pathname !== "/api/v1/tts/synthesize" ||
          target.username || target.password) {
        throw new Error("ลิงก์เสียงที่ Backend ส่งมากลับมาใช้ไม่ได้");
      }
      return audio(target, signal);
    },
    ticket: async id => (await response(ticketPath(id))).json(),
    dispatch: async (id, interaction) => (await response(`${ticketPath(id)}/dispatch`,
      json({ interaction_id: interaction }))).json(),
    englishAudio: async text => {
      if (!text.trim() || Array.from(text).length > 600) {
        throw new Error("ใส่ข้อความภาษาอังกฤษ 1–600 ตัวอักษร");
      }
      const query = new URLSearchParams({ text, lang: "en" });
      return audio(`/api/v1/tts/synthesize?${query}`);
    },
  };
}

function socketUrl(base, path) {
  const url = new URL(path, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url;
}

export function agentSocketUrl(base, interaction) {
  return socketUrl(base, `/ws/agent/${encodeURIComponent(interaction)}`);
}

export function monitorSocketUrl(base) {
  return socketUrl(base, "/ws/monitor");
}
