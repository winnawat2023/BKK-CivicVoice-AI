import { monitorSocketUrl } from "./api.mjs";
import { settings } from "./config.mjs";
import { demoCases, demoChannel } from "./demo.mjs";

const $ = id => document.getElementById(id);
const config = settings();
const frame = $("copilot");
const queue = $("queue");
const input = $("interaction-input");
const monitorStatus = $("monitor-status");
const calls = new Map();
let selected = "";
let monitor;
let reconnect;
let heartbeat;
let lastEvent;
let monitoring = false;
let demoSession;

function render() {
  const call = calls.get(selected);
  const label = !selected ? "รอเลือกสาย" : call?.ended ? "จบสายแล้ว" :
    call ? "ได้รับข้อมูลสายแล้ว" : "เปิด Copilot แล้ว";
  $("call-title").textContent = selected ? "สายที่เลือก" : "ยังไม่ได้เลือกสาย";
  $("call-id").textContent = selected || "—";
  $("call-ani").textContent = call?.maskedAni || "—";
  $("call-language").textContent = call?.language || "—";
  for (const id of ["call-state", "popup-state"]) {
    $(id).textContent = label;
    $(id).classList.toggle("live", !!call && !call.ended);
  }
  for (const [id, item] of calls) item.button.setAttribute("aria-pressed", String(id === selected));
}

function openCall(id) {
  if (!/^[a-zA-Z0-9._:-]{1,128}$/u.test(id)) {
    monitorStatus.textContent = "Conversation ID ใช้ได้เฉพาะตัวอักษร ตัวเลข และ . _ : -";
    return;
  }
  if (id === selected) return;
  selected = input.value = id;
  const url = new URL("./widget/", location.href);
  url.search = new URLSearchParams({ interaction_id: id, apiBase: config.apiBase, embedded: "true" });
  if (config.demo) {
    demoSession = crypto.randomUUID();
    url.searchParams.set("mode", "demo");
    url.searchParams.set("case", calls.get(id).demoKey);
    url.searchParams.set("workspaceSession", demoSession);
    $("desk-demo-transcript").disabled = true;
  }
  frame.src = url.href;
  frame.hidden = false;
  $("frame-placeholder").hidden = true;
  render();
}

function monitorMessage(message) {
  const { event, interaction_id: id, data } = JSON.parse(message.data);
  if (event === "connected") {
    monitorStatus.textContent = "เชื่อมต่อ Middleware แล้ว · รอ Transcript จากสาย";
    return;
  }
  if (!["transcript", "call_ended"].includes(event) || typeof id !== "string" || id.startsWith("WEB-")) return;
  let call = calls.get(id);
  if (event === "call_ended") {
    if (!call && selected !== id) return;
    if (!call) calls.set(id, { ended: true, button: document.createElement("button") });
    else {
      call.ended = true;
      call.maskedAni = "";
      call.button.remove();
    }
    render();
    return;
  }
  if (!call) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "queue-button";
    button.textContent = id;
    button.addEventListener("click", () => openCall(id));
    call = { button };
    calls.set(id, call);
    queue.prepend(button);
    if (calls.size > 30) {
      const oldest = [...calls.keys()].find(key => key !== selected);
      calls.get(oldest).button.remove();
      calls.delete(oldest);
    }
  }
  const digits = String(data?.caller_ani ?? "").replace(/\D/gu, "");
  if (digits.length >= 4) call.maskedAni = "••• " + digits.slice(-4);
  if (["th", "en"].includes(data?.language)) call.language = data.language.toUpperCase();
  render();
}

function connectMonitor() {
  monitor = new WebSocket(monitorSocketUrl(config.apiBase));
  const socket = monitor;
  socket.addEventListener("open", () => {
    lastEvent = Date.now();
    heartbeat = setInterval(() => {
      if (Date.now() - lastEvent > 45000) socket.close();
      else socket.send(JSON.stringify({ action: "ping" }));
    }, 15000);
  });
  socket.addEventListener("message", message => {
    lastEvent = Date.now();
    try {
      monitorMessage(message);
    } catch {
      monitorStatus.textContent = "ได้รับข้อมูลสายที่อ่านไม่ได้";
    }
  });
  socket.addEventListener("close", () => {
    clearInterval(heartbeat);
    if (!monitoring) return;
    monitorStatus.textContent = "การเชื่อมต่อหลุด · กำลังลองเชื่อมใหม่";
    reconnect = setTimeout(connectMonitor, 3000);
  });
}

$("interaction-form").addEventListener("submit", event => {
  event.preventDefault();
  openCall(input.value.trim());
});
$("frame-size").addEventListener("change", event => {
  const width = event.currentTarget.value;
  if (["400", "450", "500"].includes(width)) document.body.style.setProperty("--frame-width", width + "px");
});
window.addEventListener("pagehide", () => {
  monitoring = false;
  clearTimeout(reconnect);
  clearInterval(heartbeat);
  monitor?.close();
});
window.addEventListener("pageshow", () => {
  if (!config.demo && config.local && !monitoring) {
    monitoring = true;
    connectMonitor();
  }
});

if (config.demo) {
  $("interaction-form").hidden = true;
  $("desk-demo-controls").hidden = false;
  monitorStatus.textContent = "โหมดซ้อมเดโม · เลือกสายตัวอย่าง";
  for (const item of demoCases) {
    const id = item.ticket.interaction_id;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "queue-button";
    button.textContent = item.name;
    button.addEventListener("click", () => openCall(id));
    calls.set(id, { button, demoKey: item.key, maskedAni: item.ani, language: item.language });
    queue.append(button);
  }
  window.addEventListener("message", ({ source, origin, data }) => {
    if (source === frame.contentWindow && origin === location.origin &&
        data?.channel === demoChannel && data.session === demoSession && data.event === "ready") {
      $("desk-demo-transcript").disabled = false;
    }
  });
  $("desk-demo-transcript").addEventListener("click", event => {
    frame.contentWindow.postMessage({ channel: demoChannel, session: demoSession, command: "transcript" }, location.origin);
    event.currentTarget.disabled = true;
  });
} else {
  if (config.interaction) openCall(config.interaction);
  if (!config.local) monitorStatus.textContent = "เปิดสายด้วย Genesys Conversation ID";
}
render();
