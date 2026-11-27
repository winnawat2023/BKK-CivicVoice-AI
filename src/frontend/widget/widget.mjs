import { settings } from "../config.mjs";
import { middleware, agentSocketUrl } from "../api.mjs";
import { decodeEvent, updateSegments } from "../model.mjs";
import { demoCases, demoChannel } from "../demo.mjs";
import { writeDemoStatus, trackDemoTicket } from "../demo-store.mjs";
import { renderSummaryCard } from "../summary.mjs";

const $ = id => document.getElementById(id);
const speakers = { caller: "ประชาชน", agent: "1555 Agent", bot: "AI Voice" };
const elements = ["transcript", "summary", "classifications", "dispatch", "preview", "audio", "english"]
  .map($);
const [transcript, summary, classifications, dispatch, preview, audio, english] = elements;
const state = { segments: [], insight: null, ticket: null, ready: false, ended: false, saving: false };

let config;
let api;
let interaction;
let socket;
let reconnectTimer;
let heartbeat;
let reconnectCount = 0;
let lastFrame = 0;
let active = true;
let initialized = false;
let pendingCreate;
let createUncertain = false;
let audioUrl;
let audioGeneration = 0;
let demoCase;
let demoSession;

function reportDemo(event) {
  if (demoSession && window.parent !== window) {
    window.parent.postMessage({ channel: demoChannel, session: demoSession, event }, location.origin);
  }
}

function handleDemoCommand(message) {
  const payload = message.data;
  if (message.source !== window.parent || message.origin !== location.origin ||
      payload?.channel !== demoChannel || payload.session !== demoSession) return;
  if (payload.command === "transcript") {
    onEvent({ event: "transcript", data: { segment: demoCase.nextSegment } });
  } else if (payload.command === "end") {
    onEvent({ event: "call_ended" });
  }
}

function setMessage(id, message, error = false) {
  const el = $(id);
  el.textContent = message;
  el.hidden = !message;
  el.classList.toggle("error", error);
}

function setConnection(message, live = false) {
  $("connection").textContent = message;
  $("connection").classList.toggle("live", live);
}

function addText(parent, type, value, className) {
  const node = document.createElement(type);
  node.textContent = value;
  if (className) node.className = className;
  parent.append(node);
  return node;
}

function maskAni(value) {
  const digits = String(value ?? "").replace(/\D/g, "");
  return digits.length >= 7 ? `${digits.slice(0, 2)}x-xxx-${digits.slice(-4)}` : "—";
}

function renderSegment(segment) {
  const row = document.createElement("div");
  row.className = `segment ${segment.speaker}`;
  const header = addText(row, "div", "", "segment-head");
  const isEnglish = segment.source_language === "en";
  addText(header, "span", isEnglish && segment.speaker === "caller" ? "นักท่องเที่ยว" : speakers[segment.speaker]);
  const time = String(segment.ts ?? "").match(/T(\d{2}:\d{2})/u)?.[1];
  addText(header, "span", [time, !segment.is_final && "กำลังถอดเสียง"].filter(Boolean).join(" · "));

  function line(label, text) {
    const paragraph = addText(row, "p", "");
    if (label) addText(paragraph, "span", label, "lang");
    const data = state.insight ?? state.ticket;
    const terms = [data?.location_detail, data?.district && `เขต${data.district}`, data?.district];
    if (demoCase?.key === "tourist") terms.push("Sukhumvit 50", "สุขุมวิท 50");
    const matches = [...new Set(terms.filter(term =>
      typeof term === "string" && term.length >= 2
    ))].sort((a, b) => b.length - a.length);
    let cursor = 0;
    for (; cursor < text.length;) {
      const first = matches.map(term => ({ term, offset: text.indexOf(term, cursor) }))
        .filter(hit => hit.offset >= 0).sort((a, b) => a.offset - b.offset)[0];
      if (!first) break;
      paragraph.append(text.slice(cursor, first.offset));
      addText(paragraph, "mark", first.term);
      cursor = first.offset + first.term.length;
    }
    paragraph.append(text.slice(cursor));
  }
  line(isEnglish ? "EN" : "", segment.text);
  if (typeof segment.translated_text === "string" && segment.translated_text) line("TH", segment.translated_text);
  else if (isEnglish) addText(row, "small", "รอคำแปลภาษาไทย");
  return row;
}

function renderTranscript() {
  const follow = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 24;
  const previous = transcript.scrollTop;
  transcript.replaceChildren(...state.segments.map(renderSegment));
  if (!state.segments.length) addText(transcript, "p", state.ended ? "จบสายแล้ว" : "รอข้อความจากสาย", "muted");
  transcript.scrollTop = follow ? transcript.scrollHeight : previous;
  $("language").textContent = state.segments.some(segment => segment.source_language === "en") ? "EN → TH" : "TH";
}

function renderActions() {
  const saved = state.ticket?.dispatched === true;
  const mayCreate = config?.enableSocketCreate && !createUncertain &&
    state.insight?.intent === "complaint" && state.insight.district && !state.insight.provisional && !state.ended;
  dispatch.disabled = state.saving || saved || !state.ready || (!state.ticket && !mayCreate) ||
    !!state.ticket && !state.ticket.district;
  dispatch.textContent = saved ? "ส่งสำนักงานเขตแล้ว" : state.saving ? "กำลังดำเนินการ…" :
    "1-Click บันทึกคำร้อง & ส่งสำนักงานเขต";
  $("sms").disabled = !config?.demo || !state.ticket;
}

function renderInsight() {
  const data = state.insight ?? state.ticket;
  renderSummaryCard({
    list: summary, empty: $("no-summary"), tags: classifications,
    districtCard: $("district-card"), districtName: $("district-name"),
  }, data, { showUnit: true, district: state.ticket?.district });
  $("ticket").textContent = state.ticket ? `${state.ticket.ticket_id} · ${state.ticket.status ?? "รับเรื่อง"}` : "";
  renderActions();
}

function acceptTicket(ticket) {
  if (typeof ticket?.ticket_id !== "string" || !ticket.ticket_id ||
      (ticket.interaction_id && ticket.interaction_id !== interaction)) return false;
  if (state.ticket?.ticket_id === ticket.ticket_id) {
    const old = state.ticket;
    if (old.updated_at && ticket.updated_at && ticket.updated_at < old.updated_at) return true;
    const previous = old.dispatched ? { dispatched: true, dispatched_at: old.dispatched_at } : {};
    state.ticket = { ...old, ...ticket, ...previous };
  } else {
    state.ticket = ticket;
  }
  renderInsight();
  return true;
}

function stopPreview() {
  audioGeneration++;
  preview.disabled = false;
  audio.pause();
  audio.removeAttribute("src");
  audio.load();
  audio.hidden = true;
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = undefined;
  if (config?.demo && "speechSynthesis" in window) window.speechSynthesis.cancel();
}

async function previewEnglish() {
  const text = english.value.trim();
  if (!text) return setMessage("audio-status", "พิมพ์ประโยคภาษาอังกฤษก่อน");
  stopPreview();
  if (config.demo) {
    if (!("speechSynthesis" in window)) return setMessage("audio-status", "เบราว์เซอร์นี้เล่นเสียงเดโมไม่ได้");
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = "en-US";
    speech.onerror = () => setMessage("audio-status", "เครื่องนี้ไม่มีเสียงภาษาอังกฤษสำหรับเดโม");
    window.speechSynthesis.speak(speech);
    return setMessage("audio-status", "เดโม: ฟังตัวอย่างบนเครื่องนี้");
  }
  const generation = audioGeneration;
  preview.disabled = true;
  setMessage("audio-status", "กำลังสร้างเสียงตัวอย่าง…");
  try {
    const blob = await api.englishAudio(text);
    if (generation !== audioGeneration) return;
    audioUrl = URL.createObjectURL(blob);
    audio.src = audioUrl;
    audio.hidden = false;
    const playing = await audio.play().then(() => true, () => false);
    if (generation === audioGeneration && !audio.error) {
      setMessage("audio-status", playing ? "กำลังเล่นเสียงตัวอย่างสำหรับเจ้าหน้าที่" : "กดเล่นในแถบเสียงเพื่อฟังตัวอย่าง");
    }
  } catch (error) {
    if (generation === audioGeneration) setMessage("audio-status", error.message, true);
  } finally {
    if (generation === audioGeneration) preview.disabled = false;
  }
}

function settleCreate(error, ticket) {
  if (!pendingCreate) return;
  const { resolve, reject, timer } = pendingCreate;
  pendingCreate = null;
  clearTimeout(timer);
  if (error) reject(error);
  else resolve(ticket);
}

function createTicket() {
  if (socket?.readyState !== WebSocket.OPEN) return Promise.reject(new Error("WebSocket ยังไม่เชื่อมต่อ"));
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      createUncertain = true;
      settleCreate(new Error("ยังไม่ได้รับผลสร้างคำร้อง กำลังตรวจข้อมูลสายอีกครั้ง"));
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ action: "snapshot" }));
    }, 8000);
    pendingCreate = { resolve, reject, timer };
    try {
      socket.send(JSON.stringify({ action: "create_ticket" }));
    } catch (error) {
      settleCreate(error);
    }
  });
}

async function dispatchTicket() {
  if (dispatch.disabled) return;
  state.saving = true;
  renderActions();
  setMessage("action-status", "กำลังตรวจคำร้องและส่งสำนักงานเขต…");
  try {
    if (config.demo) {
      writeDemoStatus(state.ticket.ticket_id, "dispatched");
      acceptTicket({ ...trackDemoTicket(state.ticket), status: "กำลังดำเนินการ", dispatched: true });
      setMessage("action-status", `เดโม: ส่งเรื่อง ${state.ticket.ticket_id} จำลองแล้ว`);
      reportDemo("dispatched");
      return;
    }
    const ticket = state.ticket ?? await createTicket();
    if (!ticket.district) throw new Error("กรุณายืนยันเขตของคำร้องในระบบก่อนส่งต่อ");
    const result = await api.dispatch(ticket.ticket_id, interaction);
    if (result.success !== true || result.ticket?.ticket_id !== ticket.ticket_id ||
        result.ticket?.dispatched !== true || !acceptTicket(result.ticket)) {
      throw new Error(result.message || "Backend ยังไม่ยืนยันการส่งเขต");
    }
    setMessage("action-status", result.message || `ส่งเรื่อง ${state.ticket.ticket_id} แล้ว`);
  } catch (error) {
    setMessage("action-status", error.message, true);
  } finally {
    state.saving = false;
    renderActions();
  }
}

function setSegments(segments) {
  if (!Array.isArray(segments)) return;
  state.segments = segments.reduce(updateSegments, []);
  renderTranscript();
}

function onEvent({ event, data }) {
  switch (event) {
    case "connected":
      $("ani").textContent = maskAni(data.ani);
      break;
    case "snapshot": {
      if (state.ended) break;
      const session = data.session ?? data;
      if (session.interaction_id && session.interaction_id !== interaction) break;
      $("ani").textContent = maskAni(session.caller_ani ?? session.ani ?? data.ani);
      state.insight = session.analysis ?? session.summary ?? data.analysis ?? null;
      acceptTicket(data.ticket ?? session.ticket);
      setSegments(session.segments ?? session.transcript ?? []);
      state.ready = true;
      reconnectCount = 0;
      setConnection("Live Syncing", true);
      setMessage("banner", "");
      if (!state.ticket) setMessage("action-status", "รอคำร้องจาก Backend");
      renderInsight();
      break;
    }
    case "transcript":
      if (state.ended) break;
      if (data.caller_ani || data.ani) $("ani").textContent = maskAni(data.caller_ani ?? data.ani);
      state.segments = updateSegments(state.segments, data.segment ?? data);
      renderTranscript();
      break;
    case "summary":
      if (state.ended) break;
      state.insight = data.analysis ?? data.summary ?? data;
      renderInsight();
      renderTranscript();
      break;
    case "ticket":
    case "dispatch_result":
    case "ticket_result": {
      if (data.success === false) {
        if (event === "ticket_result") settleCreate(new Error(data.error || data.message || "สร้างคำร้องไม่สำเร็จ"));
        break;
      }
      const ticket = data.ticket ?? data;
      if (acceptTicket(ticket)) {
        if (event === "ticket_result" || event === "ticket") settleCreate(null, state.ticket);
        if (state.ticket.district && !state.saving) setMessage("action-status", "ตรวจสอบรายละเอียดก่อนส่งสำนักงานเขต");
        if (!state.ticket.district && !state.saving) setMessage("action-status", "ต้องยืนยันเขตก่อนส่งเรื่อง");
      }
      break;
    }
    case "live_update":
      if (state.ready || state.ended) break;
      setConnection("รับข้อมูลจาก Backend รุ่นเดิม");
      setMessage("banner", "Backend รุ่นนี้แสดงข้อมูลได้ กดส่งเขตได้เมื่อเชื่อม API 2.0");
      $("ani").textContent = maskAni(data.caller_ani);
      state.insight = data;
      setSegments([{ speaker: "caller", text: data.transcript }]);
      renderInsight();
      break;
    case "call_ended":
      state.ended = true;
      $("ani").textContent = "—";
      stopPreview();
      english.value = "";
      $("meaning").hidden = $("pronunciation").hidden = true;
      $("duplicate").hidden = true;
      state.segments = [];
      state.insight = null;
      settleCreate(new Error("สายสิ้นสุดก่อน Backend ยืนยันคำร้อง"));
      renderTranscript();
      renderInsight();
      setConnection("จบสาย");
      break;
    case "error":
      setMessage("banner", data.message || data.detail || "WebSocket แจ้งข้อผิดพลาด", true);
      break;
  }
}

function connect() {
  if (!active || state.ended) return;
  state.ready = false;
  renderActions();
  setConnection("กำลังเชื่อมต่อ…");
  const client = new WebSocket(agentSocketUrl(config.apiBase, interaction));
  socket = client;
  let openedAt = Date.now();
  client.addEventListener("open", () => {
    if (socket !== client) return;
    openedAt = lastFrame = Date.now();
    setConnection("รอข้อมูลสาย…");
    heartbeat = setInterval(() => {
      if (Date.now() - lastFrame > 45000) client.close();
      else if (!state.ready && Date.now() - openedAt > 20000) {
        setMessage("banner", "ยังไม่ได้รับ snapshot ของสาย ตรวจว่า Backend ใช้ API 2.0");
      }
      if (state.ready && client.readyState === WebSocket.OPEN) client.send(JSON.stringify({ action: "ping" }));
    }, 15000);
  });
  client.addEventListener("message", message => {
    if (!active || socket !== client) return;
    lastFrame = Date.now();
    try {
      const event = decodeEvent(message.data, interaction);
      if (event) onEvent(event);
    } catch {
      setMessage("banner", "ได้รับข้อมูลสดที่อ่านไม่ได้", true);
    }
  });
  client.addEventListener("close", () => {
    if (socket !== client) return;
    clearInterval(heartbeat);
    state.ready = false;
    if (pendingCreate) {
      createUncertain = true;
      settleCreate(new Error("การเชื่อมต่อหลุดก่อน Backend ยืนยันคำร้อง"));
    }
    renderActions();
    if (!active || state.ended) return;
    const delay = Math.min(2 ** reconnectCount++, 30);
    setConnection("หลุดการเชื่อมต่อ");
    setMessage("banner", `กำลังลองเชื่อมต่ออีกครั้งใน ${delay} วินาที`);
    reconnectTimer = setTimeout(connect, delay * 1000);
  });
}

function start() {
  config = settings();
  api = middleware(config.apiBase);
  if (config.demo) {
    const query = new URLSearchParams(location.search);
    demoCase = demoCases.find(item => item.key === query.get("case")) ?? demoCases[0];
    demoSession = query.get("workspaceSession");
  }
  interaction = demoCase?.ticket.interaction_id ?? config.interaction;
  $("interaction").textContent = interaction || "—";
  dispatch.addEventListener("click", dispatchTicket);
  preview.addEventListener("click", previewEnglish);
  audio.addEventListener("error", () => {
    if (audioUrl) setMessage("audio-status", "เบราว์เซอร์ไม่สามารถเล่นไฟล์เสียงนี้ได้", true);
  });
  english.addEventListener("input", () => {
    stopPreview();
    if (demoCase?.script) {
      const original = english.value === demoCase.script.english_text;
      $("meaning").hidden = $("pronunciation").hidden = !original;
    }
    setMessage("audio-status", "ฟังตัวอย่างประโยคที่แก้ไขแล้ว");
  });
  $("sms").addEventListener("click", () => {
    setMessage("action-status", "เดโม: จำลองข้อความขอพิกัดและรูปภาพแล้ว");
    const link = $("sms-demo-link");
    const url = new URL("../tracking/", location.href);
    url.search = new URLSearchParams({ mode: "demo", ticket: state.ticket.ticket_id,
      stage: state.ticket.dispatched ? "working" : "received" });
    link.href = url.href;
    link.hidden = false;
    reportDemo("sms-preview");
  });
  if (config.demo) {
    state.ready = true;
    state.insight = demoCase.ticket;
    $("ani").textContent = demoCase.ani;
    if (demoCase.script) {
      english.value = demoCase.script.english_text;
      setMessage("meaning", `ความหมาย: ${demoCase.script.thai_meaning}`);
      setMessage("pronunciation", `คำอ่าน: ${demoCase.script.thai_pronunciation}`);
    }
    setConnection("ข้อมูลสาธิต");
    setSegments(demoCase.segments);
    acceptTicket(trackDemoTicket(demoCase.ticket));
    $("duplicate").hidden = !demoCase.duplicate;
    setMessage("action-status", "โหมดเดโม · ทดสอบคำสั่งโดยไม่ส่งเรื่องหรือ SMS จริง");
    if (demoSession && window.parent !== window) {
      document.body.classList.add("embedded-widget");
      $("widget-demo-links").hidden = true;
      window.addEventListener("message", handleDemoCommand);
      reportDemo("ready");
    }
  } else if (interaction) {
    if (new URLSearchParams(location.search).get("embedded") === "true" && window.parent !== window) {
      document.body.classList.add("embedded-widget");
    }
    $("widget-demo-links").hidden = true;
    setMessage("audio-status", "ฟังเสียงตัวอย่างได้ ส่วนการส่งเข้าคู่สายรอ Genesys");
    connect();
  } else {
    $("widget-demo-links").hidden = true;
    setMessage("banner", "เปิดจากโต๊ะเจ้าหน้าที่หรือระบุ Genesys Conversation ID");
  }
  renderActions();
}

window.addEventListener("pagehide", () => {
  active = false;
  clearTimeout(reconnectTimer);
  clearInterval(heartbeat);
  socket?.close();
  stopPreview();
});

window.addEventListener("pageshow", entry => {
  if (!entry.persisted || !initialized) return;
  active = true;
  if (!config.demo && interaction && !state.ended) connect();
});

try {
  start();
  initialized = true;
} catch (error) {
  setMessage("banner", error.message, true);
}
