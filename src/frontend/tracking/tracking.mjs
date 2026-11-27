import { settings } from "../config.mjs";
import { middleware } from "../api.mjs";
import { timeline, trackingStep } from "../model.mjs";
import { demoCases } from "../demo.mjs";
import { demoStoragePrefix, storedDemoStatus, trackDemoTicket } from "../demo-store.mjs";

const $ = id => document.getElementById(id);
let imageUrl;
const status = (message, isError = false) => {
  $("tracking-status").textContent = message;
  $("tracking-status").classList.toggle("error", isError);
};

function render(ticket) {
  const step = trackingStep(ticket);
  const sent = ticket.dispatched === true || !!ticket.dispatched_at;
  $("ticket-id").textContent = ticket.ticket_id;
  $("issue").textContent = ticket.summary_lines?.[0] || ticket.sub_category || ticket.category || "คำร้อง";
  $("location").textContent = [ticket.location_detail, ticket.district && `เขต${ticket.district}`]
    .filter(Boolean).join(" · ");
  $("timeline").replaceChildren();
  timeline.forEach((label, i) => {
    const confirmed = i !== 1 || sent;
    const current = confirmed && i === step;
    const done = confirmed && (i < step || i === 3 && i === step);
    const item = document.createElement("li");
    item.className = done ? "done" : current ? "current" : "pending";
    if (current) item.setAttribute("aria-current", "step");
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.textContent = done ? "✓" : String(i + 1);
    dot.setAttribute("aria-hidden", "true");
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = label;
    const detail = document.createElement("small");
    const date = [ticket.created_at, ticket.dispatched_at, null, current && ticket.updated_at][i];
    const when = typeof date === "string" ? date.slice(0, 16).replace("T", " ") : null;
    detail.textContent = when || (done ? "ยืนยันแล้ว" : current ? "สถานะปัจจุบัน" :
      i === 1 && step > 1 ? "ยังไม่มีข้อมูลยืนยันการส่งเขต" : "ยังไม่ถึงขั้นตอนนี้");
    copy.append(title, detail);
    item.append(dot, copy);
    $("timeline").append(item);
  });
  $("details").hidden = false;
  $("progress").hidden = false;
}

function enableDemoEvidence() {
  $("evidence").hidden = false;
  const gps = $("gps");
  const photo = $("photo");
  const file = $("file");
  const preview = $("photo-preview");
  const evidence = $("evidence-status");
  evidence.textContent = "ข้อมูลเดโมอยู่บนหน้านี้เท่านั้น";
  gps.disabled = photo.disabled = false;
  gps.addEventListener("click", () => {
    evidence.textContent = "พิกัดตัวอย่าง 13.7080, 100.5930 · ยังไม่ได้ส่งข้อมูล";
  });
  photo.addEventListener("click", () => {
    file.hidden = false;
    file.focus();
    file.click();
  });
  file.addEventListener("change", () => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    imageUrl = undefined;
    preview.removeAttribute("src");
    preview.hidden = true;
    const selected = file.files[0];
    if (!selected) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(selected.type) ||
        selected.size > 5 * 1024 ** 2) {
      evidence.textContent = "เลือกภาพ JPEG, PNG หรือ WebP ขนาดไม่เกิน 5 MB";
      return;
    }
    imageUrl = URL.createObjectURL(selected);
    preview.src = imageUrl;
    preview.hidden = false;
    evidence.textContent = "แสดงตัวอย่างบนเครื่อง · ยังไม่ได้อัปโหลด";
  });
}

async function enableSmsEvidence(config) {
  const token = new URLSearchParams(location.hash.slice(1)).get("token");
  if (!token) throw new Error("ลิงก์นี้ไม่มีรหัสสำหรับส่งข้อมูล");
  const api = middleware(config.smsBase);
  const evidence = await api.evidence(token);
  if (!evidence?.ticket_id) throw new Error("ระบบยังไม่ยืนยันคำร้องสำหรับลิงก์นี้");
  status(evidence.state === "mock" ? "ลิงก์สำหรับทดสอบส่งข้อมูลประกอบ" : "เพิ่มรูป พิกัด หรือลิงก์แผนที่ประกอบคำร้อง");
  $("ticket-id").textContent = evidence.ticket_id;
  $("issue").textContent = "ส่งตำแหน่งหรือรูปที่เกี่ยวข้องกับจุดเกิดเหตุ";
  $("details").hidden = false;
  if (evidence.tracking?.ticket_id === evidence.ticket_id) render(evidence.tracking);
  $("evidence").hidden = false;

  const selectGps = $("gps");
  const selectPhoto = $("photo");
  const saveGps = $("save-gps");
  const savePhoto = $("save-photo");
  const feedback = $("evidence-status");
  const coordinates = $("evidence-coordinates");
  const file = $("file");
  const preview = $("photo-preview");
  const mapForm = $("map-form");
  const mapInput = $("map-link");
  const saveMap = $("save-map");
  const savedMap = $("saved-map-link");
  let candidate;
  let photo;

  feedback.textContent = evidence.has_photo ? "มีรูปภาพบันทึกไว้แล้ว" : "ตรวจข้อมูลก่อนกดยืนยันส่ง";
  function showLocation(location, label) {
    coordinates.hidden = false;
    coordinates.textContent = label + " " + location.latitude.toFixed(5) + ", " + location.longitude.toFixed(5);
  }
  if (typeof evidence.latitude === "number" && typeof evidence.longitude === "number") {
    showLocation(evidence, "พิกัดที่บันทึกแล้ว");
  }
  selectGps.disabled = !navigator.geolocation;
  selectPhoto.disabled = false;
  mapForm.hidden = false;

  function showMap(url) {
    if (!url) return;
    mapInput.value = url;
    savedMap.href = url;
    savedMap.hidden = false;
  }
  showMap(evidence.map_url);

  selectGps.addEventListener("click", () => {
    selectGps.disabled = true;
    saveGps.hidden = true;
    candidate = undefined;
    feedback.textContent = "กำลังขอพิกัดปัจจุบัน…";
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      candidate = { latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy };
      showLocation(candidate, "พิกัดปัจจุบัน");
      saveGps.hidden = false;
      selectGps.disabled = false;
      feedback.textContent = "ตรวจว่าพิกัดปัจจุบันคือจุดเกิดเหตุก่อนส่ง";
    }, () => {
      selectGps.disabled = false;
      feedback.textContent = "อ่านพิกัดไม่ได้ · ตรวจสิทธิ์ตำแหน่งของเบราว์เซอร์";
    }, { enableHighAccuracy: true, timeout: 10000 });
  });

  selectPhoto.addEventListener("click", () => {
    file.hidden = false;
    file.click();
  });
  file.addEventListener("change", () => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    imageUrl = undefined;
    photo = file.files[0];
    preview.hidden = savePhoto.hidden = true;
    preview.removeAttribute("src");
    if (!photo) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(photo.type) || photo.size > 5 * 1024 ** 2) {
      feedback.textContent = "เลือก JPEG, PNG หรือ WebP ขนาดไม่เกิน 5 MB";
      photo = undefined;
      return;
    }
    imageUrl = URL.createObjectURL(photo);
    preview.src = imageUrl;
    preview.hidden = savePhoto.hidden = false;
    feedback.textContent = "ตรวจรูปก่อนส่ง";
  });

  async function save(button, input, label, operation, { hideButton = true } = {}) {
    button.disabled = input.disabled = true;
    feedback.textContent = "กำลังบันทึก…";
    try {
      const saved = await operation();
      if (hideButton) button.hidden = true;
      feedback.textContent = "บันทึก" + label + "เข้าคำร้องแล้ว";
      return saved;
    } catch (error) {
      feedback.textContent = error.message || "บันทึกข้อมูลไม่ได้";
    } finally {
      button.disabled = input.disabled = false;
    }
  }

  saveGps.addEventListener("click", async () => {
    if (!candidate) return;
    const saved = await save(saveGps, selectGps, "พิกัด", () => api.saveLocation(token, candidate));
    if (saved) showLocation(saved, "พิกัดที่บันทึกแล้ว");
  });
  savePhoto.addEventListener("click", () => {
    if (photo) void save(savePhoto, file, "รูป", () => api.savePhoto(token, photo));
  });
  mapForm.addEventListener("submit", async event => {
    event.preventDefault();
    const result = await save(saveMap, mapInput, "ลิงก์แผนที่", () => api.saveMapLink(token, mapInput.value.trim()),
                              { hideButton: false });
    if (result) showMap(result.map_url);
  });
}

async function start() {
  const config = settings();
  if (new URLSearchParams(location.search).get("mode") === "evidence") {
    await enableSmsEvidence(config);
    return;
  }
  if (config.demo) {
    const demo = config.ticketId ? demoCases.find(item => item.ticket.ticket_id === config.ticketId) : demoCases[0];
    if (!demo) {
      status("ไม่พบคำร้องตัวอย่าง", true);
      return;
    }
    const received = new URLSearchParams(location.search).get("stage") === "received";
    function renderDemoStatus() {
      const stored = storedDemoStatus(demo.ticket.ticket_id);
      const fallback = received ? null : { stage: "dispatched", at: "2026-11-25T10:30:00" };
      render(trackDemoTicket(demo.ticket, stored ?? fallback));
    }
    renderDemoStatus();
    window.addEventListener("storage", event => {
      if (event.key === demoStoragePrefix + demo.ticket.ticket_id) renderDemoStatus();
    });
    status("คำร้องตัวอย่าง · โหมดเดโม");
    enableDemoEvidence();
    return;
  }
  if (!config.internal && !config.local) {
    status("เปิดลิงก์ที่ได้รับทาง SMS เพื่อดูหรือเพิ่มข้อมูลประกอบคำร้อง");
    return;
  }
  $("tracking-search").hidden = false;
  $("tracking-api-base").value = config.apiBase;
  $("tracking-ticket").value = config.ticketId;
  if (!config.ticketId) {
    status("กรอกเลขคำร้องเพื่อดูสถานะจาก Middleware");
    return;
  }
  const ticket = await middleware(config.apiBase).ticket(config.ticketId);
  if (ticket?.ticket_id !== config.ticketId) throw new Error("Backend ส่งข้อมูลคำร้องไม่ตรงกับเลขที่ขอ");
  render(ticket);
  status("มุมมองภายใน · ข้อมูลจาก Backend");
}

start().catch(error => status(error.message, true));
window.addEventListener("pagehide", () => {
  if (imageUrl) URL.revokeObjectURL(imageUrl);
});
