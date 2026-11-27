import { settings } from "./config.mjs";
import { middleware, MiddlewareError } from "./api.mjs";
import { renderSummaryCard } from "./summary.mjs";
import { showCitizenSms, resetCitizenSms, updateSmsReview } from "./citizen-sms.mjs";
import { createVoiceSession, supportsVoice } from "./voice-session.mjs";

const $ = id => document.getElementById(id);
const panel = $("voice-panel");
const launcher = $("voice-launcher");
const status = $("voice-status");
const transcript = $("voice-transcript");
const area = $("voice-area");
const locationToggle = $("voice-location-toggle");
const locationEditor = $("voice-location");
const districtSelect = $("voice-district-select");
const locationInput = $("voice-location-detail");
const greeting = "สวัสดีค่ะ ต้องการแจ้งปัญหาเมืองหรือสอบถามวิธีติดตามคำร้องคะ";
let config;
let api;
let asr;
let sms;
let ready = false;
let phase = "intro";
let busy = false;
let interaction;
let turns = [];
let assessment;
let confirmed = false;
let confirmationUncertain = false;
let session;
let focusReturn = launcher;
let districts;
let locationExpanded = false;

function render() {
  $("voice-intro").hidden = phase !== "intro";
  $("voice-chat").hidden = phase !== "chat";
  $("voice-review").hidden = phase !== "review";
  $("voice-start").disabled = !ready || busy;
  $("voice-finish").disabled = busy;
  $("voice-confirm").disabled = busy || !assessment?.canSubmit || confirmed || confirmationUncertain;
  $("voice-back").disabled = busy || confirmed || confirmationUncertain;
  $("voice-reset").disabled = busy;
  const isComplaint = assessment?.insight.intent === "complaint";
  const canEdit = isComplaint && !confirmed && !confirmationUncertain;
  area.hidden = !isComplaint;
  locationToggle.hidden = !canEdit;
  locationToggle.disabled = busy;
  locationToggle.setAttribute("aria-expanded", String(!!canEdit && locationExpanded));
  locationEditor.hidden = !canEdit || !locationExpanded;
  locationEditor.disabled = busy || !canEdit;
}

function setStatus(text, state = "waiting") {
  status.textContent = text;
  $("voice-indicator").dataset.state = state;
}

function appendTranscript(role, text) {
  const row = document.createElement("li");
  const label = document.createElement("strong");
  const content = document.createElement("p");
  const follow = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 28;
  row.className = role === "user" ? "caller" : "assistant";
  label.textContent = role === "user" ? "คุณ" : "AI Voice";
  content.textContent = text;
  row.append(label, content);
  transcript.append(row);
  if (follow) transcript.scrollTop = transcript.scrollHeight;
}

function showPanel(open, source = launcher) {
  if (panel.hidden === !open) return;
  panel.hidden = !open;
  launcher.setAttribute("aria-expanded", String(open));
  if (open) {
    focusReturn = source;
    (phase === "chat" ? $("voice-finish") : $("voice-close")).focus();
  } else {
    if (phase === "chat" && !busy) {
      session?.voice.cancel();
      session = undefined;
      turns = [];
      transcript.replaceChildren();
      interaction = undefined;
      phase = "intro";
      setStatus("");
      render();
    }
    focusReturn.focus();
  }
}

function startConversation() {
  const current = {};
  const firstTurn = !transcript.childElementCount;
  try {
    current.voice = createVoiceSession({
      greeting: firstTurn ? {
        text: greeting,
        url: "/api/v1/tts/synthesize?" + new URLSearchParams({ text: greeting, lang: "th" }),
      } : undefined,
      transcribe: asr.transcribe,
      synthesize: api.voiceReplyAudio,
      onState(text, state) { if (session === current && !busy) setStatus(text, state); },
      onAssistantText(text) { if (session === current) appendTranscript("assistant", text); },
      async respond(value, signal, shouldReply) {
        if (session !== current) return;
        const message = Array.from(value.trim()).slice(0, 300).join("");
        const history = turns.slice(-12);
        turns.push({ role: "user", content: message });
        appendTranscript("user", message);
        if (!shouldReply) return;
        if (!busy) setStatus("AI กำลังคิด…");
        const answer = await api.voiceTurn({ message, language: "th", conversation_history: history }, signal);
        if (session !== current) return;
        if (!answer?.success || !answer.reply_text) throw new Error("Voicebot ยังไม่ได้ส่งคำตอบ");
        turns.push({ role: "assistant", content: answer.reply_text });
        return answer;
      },
    });
    session = current;
    phase = "chat";
    current.finished = current.voice.run().catch(() => {
      if (session === current && !busy) setStatus("เปิดไมโครโฟนไม่ได้ · ตรวจสิทธิ์ไมโครโฟนแล้วเริ่มใหม่");
    });
    render();
    $("voice-finish").focus();
  } catch {
    setStatus("เปิดระบบเสียงไม่ได้ · กรุณาลองอีกครั้ง");
  }
}

function setReviewNote(note = "") {
  $("voice-review-note").textContent = note;
  $("voice-review-note").hidden = !note;
}

async function prepareLocation(analysis) {
  if (!districts) {
    const result = await api.districts();
    if (!Array.isArray(result?.districts) || new Set(result.districts).size !== 50) {
      throw new Error("โหลดรายชื่อเขตกรุงเทพมหานครไม่ครบ");
    }
    districts = result.districts.toSorted(new Intl.Collator("th").compare);
    districtSelect.replaceChildren(
      new Option("เลือกเขตที่เกิดเหตุ", ""),
      ...districts.map(name => new Option("เขต" + name, name)),
    );
  }
  const district = String(analysis.district ?? "").replace(/^(?:สำนักงานเขต|เขต)\s*/u, "").trim();
  districtSelect.value = districts.includes(district) ? district : "";
  locationInput.value = String(analysis.location_detail ?? "").slice(0, 240);
  locationExpanded = false;
  assessment.initialLocation = reviewedLocation();
}

function reviewedLocation() {
  return { district: districtSelect.value || null, location_detail: locationInput.value.trim() };
}

function renderReview() {
  let insight = assessment.insight;
  if (insight.intent === "complaint") {
    const location = reviewedLocation();
    insight = { ...insight, ...location };
    const locationPreview = $("voice-location-preview");
    locationPreview.textContent = location.location_detail || (location.district ? "" : "ยังไม่ระบุพื้นที่เกิดเหตุ");
    locationPreview.hidden = !locationPreview.textContent;
    assessment.canSubmit = !!(location.district || location.location_detail);
    setReviewNote(assessment.canSubmit ? "" : "กดระบุสถานที่เพิ่มเติมก่อนยืนยันแจ้งปัญหา");
    updateSmsReview(assessment.canSubmit);
    if (location.district !== assessment.initialLocation.district ||
        location.location_detail !== assessment.initialLocation.location_detail) {
      const place = [location.location_detail, location.district && "เขต" + location.district].filter(Boolean).join(" ");
      insight = { ...insight, summary_lines: [
        "แจ้งปัญหา: " + (insight.sub_category || insight.category || "อื่น ๆ"),
        "สถานที่: " + (place || "ยังไม่ระบุสถานที่"),
      ] };
    }
  }
  renderSummaryCard({
    list: $("voice-summary"), empty: $("voice-no-summary"), tags: $("voice-classifications"),
    districtCard: $("voice-district-card"), districtName: $("voice-district-name"),
  }, insight);
  render();
}

async function finish() {
  if (busy || phase !== "chat") return;
  busy = true;
  render();
  setStatus("กำลังสรุปเรื่อง…");
  try {
    session?.voice.finish();
    await session?.finished;
    const text = Array.from(turns.filter(turn => turn.role === "user").map(turn => turn.content).join(" ")).slice(-2000).join("");
    assessment = { text, canSubmit: false, insight: { summary_th: "ยังไม่ได้รับรายละเอียดจากบทสนทนา" } };
    if (text) {
      const payload = await api.classify(text);
      const analysis = payload?.analysis ?? payload;
      if (typeof analysis?.intent !== "string") throw new Error("Backend ยังไม่ได้ส่งผลวิเคราะห์");
      assessment = { text, insight: analysis, canSubmit: false };
      if (analysis.intent === "complaint") await prepareLocation(analysis);
    }
    setReviewNote("");
    resetCitizenSms({ review: true });
    phase = "review";
    renderReview();
    setStatus("");
  } catch {
    setStatus("สรุปเรื่องไม่ได้ · กดจบการสนทนาเพื่อลองสรุปอีกครั้ง");
  } finally {
    session = undefined;
    busy = false;
    render();
    if (phase === "review" && !panel.hidden) {
      ($("voice-confirm").disabled ? $("voice-back") : $("voice-confirm")).focus();
    }
  }
}

function showTicket(id, grant) {
  confirmed = true;
  $("voice-ticket").textContent = "เลขคำร้อง " + id;
  $("voice-ticket").hidden = false;
  showCitizenSms(grant, sms, config.local);
  if (config.local) {
    const link = $("voice-tracking");
    const url = new URL("./tracking/", location.href);
    url.search = new URLSearchParams({ mode: "internal", ticket: id, apiBase: config.apiBase });
    link.href = url.href;
    link.hidden = false;
  }
}

async function confirmReport() {
  if (phase !== "review" || busy || confirmed || confirmationUncertain || !assessment?.canSubmit) return;
  busy = true;
  render();
  status.textContent = "กำลังยืนยันคำร้อง…";
  try {
    const request = { message: assessment.text, language: "th", interaction_id: interaction,
      reviewed_location: reviewedLocation() };
    const smsReady = await sms.smsHealth().then(result => result.ready === true &&
      (result.requires_gateway === true || (config.local && result.mode === "mock")), () => false);
    const outcome = smsReady ? await sms.confirmWithSms(request) : await api.voiceTurn(request);
    if (outcome?.success !== true) throw new Error("Backend ยังไม่ยืนยันการสร้างคำร้อง");
    if (typeof outcome.ticket_id === "string" && outcome.ticket_id.trim()) {
      showTicket(outcome.ticket_id, outcome.sms_grant);
      status.textContent = "Backend ยืนยันเลขคำร้องแล้ว";
    } else if (outcome.next_action === "ask_location" || outcome.next_action === "ask_repeat") {
      setReviewNote(outcome.reply_text || "กรุณากลับไปคุยต่อเพื่อเพิ่มรายละเอียด");
      assessment.canSubmit = false;
      status.textContent = "Backend ขอข้อมูลเพิ่มเติม";
    } else {
      confirmationUncertain = true;
      status.textContent = "Backend ยังไม่ระบุเลขคำร้อง · ตรวจสอบก่อนส่งอีกครั้ง";
    }
  } catch (error) {
    confirmationUncertain = !(error instanceof MiddlewareError && [400, 401, 403, 404, 422].includes(error.status));
    status.textContent = confirmationUncertain
      ? "ยังยืนยันผลไม่ได้ · ตรวจสอบคำร้องในระบบก่อนเริ่มรายการใหม่" : error.message;
  } finally {
    busy = false;
    render();
  }
}


launcher.addEventListener("click", () => showPanel(panel.hidden));
$("nav-voice").addEventListener("click", event => showPanel(true, event.currentTarget));
$("voice-close").addEventListener("click", () => showPanel(false));
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !panel.hidden) showPanel(false);
});
for (const button of document.querySelectorAll("[data-topic]")) {
  button.addEventListener("click", () => showPanel(true, button));
}
$("voice-start").addEventListener("click", () => {
  interaction ??= "WEB-" + crypto.randomUUID();
  startConversation();
});
$("voice-finish").addEventListener("click", finish);
locationToggle.addEventListener("click", () => {
  locationExpanded = !locationExpanded;
  render();
  if (locationExpanded) districtSelect.focus();
});
districtSelect.addEventListener("change", renderReview);
locationInput.addEventListener("input", renderReview);
$("voice-confirm").addEventListener("click", confirmReport);
$("voice-back").addEventListener("click", startConversation);
$("voice-reset").addEventListener("click", () => {
  phase = "intro";
  turns = [];
  transcript.replaceChildren();
  interaction = undefined;
  assessment = undefined;
  confirmed = confirmationUncertain = false;
  $("voice-ticket").hidden = $("voice-tracking").hidden = true;
  resetCitizenSms();
  setStatus("");
  render();
  $("voice-start").focus();
});
window.addEventListener("pagehide", () => {
  session?.voice.cancel();
});

async function prepare() {
  config = settings();
  if (!config.citizenLive || !supportsVoice()) {
    setStatus("อุปกรณ์หรือเว็บไซต์นี้ยังใช้ไมค์บนเว็บไม่ได้");
    return;
  }
  api = middleware(config.apiBase);
  asr = middleware(config.asrBase);
  sms = middleware(config.smsBase);
  if ((await api.health())?.status !== "ok") throw new Error("Backend ยังไม่พร้อม");
  ready = true;
  render();
}

prepare().catch(() => setStatus("บริการสนทนาบนเว็บยังเชื่อมต่อไม่ได้"));
