import { demoCases } from "./demo.mjs";

export const demoStoragePrefix = "bkk-civicvoice-demo:";
const known = id => demoCases.some(item => item.ticket.ticket_id === id);

export function storedDemoStatus(id) {
  if (!known(id)) return null;
  try {
    const value = JSON.parse(localStorage.getItem(demoStoragePrefix + id));
    return ["received", "dispatched"].includes(value?.stage) && typeof value.at === "string"
      ? value : null;
  } catch {
    return null;
  }
}

export function writeDemoStatus(id, stage) {
  if (!known(id) || !["received", "dispatched"].includes(stage)) return;
  if (storedDemoStatus(id)?.stage === "dispatched") return;
  try {
    localStorage.setItem(demoStoragePrefix + id, JSON.stringify({ stage, at: new Date().toISOString() }));
  } catch {
    // The page still runs with fixtures if browser storage is unavailable.
  }
}

export function clearDemoStatus() {
  try {
    for (const item of demoCases) localStorage.removeItem(demoStoragePrefix + item.ticket.ticket_id);
  } catch {
    // No browser storage to clear.
  }
}

export function trackDemoTicket(ticket, state = storedDemoStatus(ticket.ticket_id)) {
  if (state?.stage !== "dispatched") return { ...ticket };
  return { ...ticket, status: "กำลังดำเนินการ", dispatched: true, dispatched_at: state.at };
}
