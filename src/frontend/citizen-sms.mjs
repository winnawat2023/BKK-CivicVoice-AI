const $ = id => document.getElementById(id);
const section = $("voice-sms");
const form = $("voice-sms-form");
const phone = $("voice-sms-phone");
const submit = $("voice-sms-send");
const feedback = $("voice-sms-status");
const demoLink = $("voice-sms-demo-link");
let session;

function message(text, error = false) {
  feedback.hidden = !text;
  feedback.textContent = text;
  feedback.classList.toggle("sms-error", error);
}

export function resetCitizenSms({ review = false, canSubmit = false } = {}) {
  session = undefined;
  section.hidden = !review;
  phone.value = "";
  submit.disabled = true;
  demoLink.hidden = true;
  demoLink.removeAttribute("href");
  updateSmsReview(canSubmit);
}

export function updateSmsReview(canSubmit) {
  phone.disabled = !canSubmit;
  message(canSubmit ? "ส่ง SMS ได้หลังยืนยันแจ้งปัญหา" : "");
}

export function showCitizenSms(grant, client, local) {
  session = { grant, client, local, locked: false };
  phone.disabled = submit.disabled = !grant;
  message(grant ? "" : "บันทึกคำร้องแล้ว · บริการส่ง SMS ยังไม่พร้อม");
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const current = session;
  if (!current?.grant || current.locked || submit.disabled) return;
  const number = phone.value.trim().replace(/[ -]/g, "");
  if (!/^(?:0|\+?66)[689][0-9]{8}$/u.test(number)) {
    message("กรุณาใส่เบอร์มือถือไทยให้ถูกต้อง", true);
    phone.focus();
    return;
  }
  phone.disabled = submit.disabled = true;
  message("กำลังส่ง SMS…");
  try {
    const outcome = await current.client.sendEvidenceSms(current.grant, number);
    if (session !== current) return;
    if (current.local && outcome.status === "mock") {
      const url = new URL(outcome.evidence_url);
      if (url.origin !== location.origin || url.pathname !== "/tracking/" ||
          url.searchParams.get("mode") !== "evidence" || !new URLSearchParams(url.hash.slice(1)).has("token")) {
        throw new Error("ลิงก์ SMS จำลองต้องใช้ origin เดียวกับหน้าเว็บ");
      }
      demoLink.href = url.href;
      demoLink.hidden = false;
      message("สร้างลิงก์ SMS จำลองแล้ว · ไม่ใช้เครดิต");
    } else if (outcome.status === "accepted") {
      message("ผู้ให้บริการรับคำขอส่ง SMS แล้ว");
    } else {
      throw new Error("ยังยืนยันผลการส่ง SMS ไม่ได้");
    }
    current.locked = true;
    phone.value = "";
    feedback.focus();
  } catch (error) {
    if (session !== current) return;
    if (!error.status || error.status === 409 || error.status >= 500) current.locked = true;
    message(error.message || "ยังยืนยันผลไม่ได้ กรุณาตรวจสอบก่อนส่งใหม่", true);
  } finally {
    if (session === current) phone.disabled = submit.disabled = current.locked;
  }
});
