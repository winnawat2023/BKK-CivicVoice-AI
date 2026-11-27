#!/usr/bin/env python3
"""Live smoke test for every BKK CivicVoice API route and both WebSockets.

It talks to a server that is already running; it does not start one.

    python src/tests/smoke_api.py --base http://127.0.0.1:8000
    python src/tests/smoke_api.py --base http://127.0.0.1:8000 --skip-tts --skip-llm

Options:
    --skip-tts   skip /api/v1/tts/synthesize (edge-tts needs internet access)
    --skip-llm   skip the check that the vLLM server answers

WARNING: this writes real data (tickets, status changes, dispatches) into the server's database.
Run it against a server that uses a disposable database, e.g. DB_PATH=/tmp/smoke.db on Linux.
Every call uses a unique SMOKE-... interaction ID, so repeated runs don't collide.

Exit code: 0 if every check passed (skips are allowed), 1 if any check failed, 2 if the server is unreachable.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx
from websockets.sync.client import connect as ws_connect

if hasattr(sys.stdout, "reconfigure"):  # Thai text must not crash a Windows console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class Skip(Exception):
    """A check that cannot run here (flag given, or it depends on an earlier check that failed)."""


@dataclass
class Ctx:
    client: httpx.Client
    ws_base: str
    skip_tts: bool
    skip_llm: bool
    state: dict[str, Any] = field(default_factory=dict)

    def new_id(self, label: str) -> str:
        return f"SMOKE-{label}-{uuid.uuid4().hex[:8]}"


TESTS: list[tuple[str, Callable[[Ctx], None]]] = []


def check(name: str):
    def register(fn: Callable[[Ctx], None]):
        TESTS.append((name, fn))
        return fn

    return register


def need(c: Ctx, key: str) -> Any:
    if key not in c.state:
        raise Skip(f"depends on an earlier check that failed (missing {key})")
    return c.state[key]


def expect(response: httpx.Response, status: int = 200) -> Any:
    assert response.status_code == status, f"HTTP {response.status_code} (expected {status}): {response.text[:300]}"
    try:
        return response.json()
    except ValueError:
        return {}


def recv_until(ws, event: str, interaction_id: str | None = None, max_messages: int = 30) -> dict:
    """Read WebSocket messages until one matches; other events (transcript, snapshot...) are skipped."""
    for _ in range(max_messages):
        message = json.loads(ws.recv(timeout=10))  # raises TimeoutError if nothing arrives
        if message.get("event") == event and (interaction_id is None or message.get("interaction_id") == interaction_id):
            return message
    raise AssertionError(f"event {event!r} for {interaction_id or 'any call'} was not received")


# ----------------------------------------------------------------- health
@check("GET / says the service is online")
def _root(c: Ctx) -> None:
    body = expect(c.client.get("/"))
    assert body.get("status") == "online", body


@check("GET /api/v1/health")
def _health(c: Ctx) -> None:
    body = expect(c.client.get("/api/v1/health"))
    assert body.get("status") == "ok" and "tickets" in body, body


@check("GET /api/v1/health?check_llm=true reaches the vLLM server")
def _health_llm(c: Ctx) -> None:
    if c.skip_llm:
        raise Skip("--skip-llm")
    body = expect(c.client.get("/api/v1/health", params={"check_llm": "true"}))
    if not body.get("llm_enabled"):
        raise Skip("LLM_ENABLED=false on this server")
    assert (body.get("llm") or {}).get("reachable") is True, body.get("llm")


# ------------------------------------------------------------ AI endpoints
@check("POST /api/v1/civic/classify understands a complaint")
def _classify(c: Ctx) -> None:
    body = expect(
        c.client.post("/api/v1/civic/classify", json={"text": "ท่อระบายน้ำแตก น้ำท่วมถนน ซอยสุขุมวิท 50"})
    )
    assert body["intent"] == "complaint" and body["category"], body
    assert len(body["summary_lines"]) == 3, body["summary_lines"]


@check("POST /api/v1/civic/ask answers from the regulations")
def _ask_answer(c: Ctx) -> None:
    body = expect(c.client.post("/api/v1/civic/ask", json={"text": "วันเสาร์นี้เขตเปิดทำบัตรประชาชนไหมครับ"}))
    assert body["answered"] is True and body["answer"] and body["sources"], body


@check("POST /api/v1/civic/ask declines and offers a transfer when out of scope")
def _ask_decline(c: Ctx) -> None:
    body = expect(c.client.post("/api/v1/civic/ask", json={"text": "ขอใบอนุญาตก่อสร้างอาคารสูงต้องทำอย่างไร"}))
    assert body["answered"] is False and body["transfer_to_agent"] is True, body


# ------------------------------------------------------------- Genesys webhook
@check("POST /api/v1/genesys/webhook: a complaint creates a ticket")
def _webhook_complaint(c: Ctx) -> None:
    iid = c.state["complaint_iid"] = c.new_id("CALL")
    body = expect(
        c.client.post(
            "/api/v1/genesys/webhook",
            json={
                "interaction_id": iid,
                "ani": "0812345678",
                "dnis": "02-096-6763",
                "channel": "voice",
                "transcript": "แถวซอยสุขุมวิท 50 มีท่อระบายน้ำแตก น้ำท่วมถนน ช่วยส่งคนมาดูด้วยครับ",
            },
        )
    )
    assert body["next_action"] == "ticket_created", body
    assert body["ticket_id"] and body["ticket_id"].startswith("BKK-"), body
    assert body["reply_text"] and body["tts_audio_url"].startswith("/api/v1/tts/"), body
    c.state["ticket_id"] = body["ticket_id"]


@check("webhook: the same call again does not create a second ticket")
def _webhook_duplicate(c: Ctx) -> None:
    iid = need(c, "complaint_iid")
    body = expect(
        c.client.post("/api/v1/genesys/webhook", json={"interaction_id": iid, "transcript": "น้ำท่วมอีกครั้ง"})
    )
    assert body["duplicate"] is True and body["ticket_id"] == need(c, "ticket_id"), body


@check("webhook: an inquiry is answered and creates no ticket")
def _webhook_inquiry(c: Ctx) -> None:
    body = expect(
        c.client.post(
            "/api/v1/genesys/webhook",
            json={
                "interaction_id": c.new_id("INQ"),
                "transcript": "วันเสาร์นี้สำนักงานเขตจตุจักรเปิดทำบัตรประชาชนไหมครับ",
            },
        )
    )
    assert body["next_action"] in ("answer", "transfer_to_agent"), body
    assert body["ticket_id"] is None, body


@check("webhook: a body without transcript is rejected with 422")
def _webhook_validation(c: Ctx) -> None:
    expect(c.client.post("/api/v1/genesys/webhook", json={"interaction_id": c.new_id("BAD")}), 422)


# -------------------------------------------------------------------- tickets
@check("GET /api/v1/tickets lists the new ticket")
def _tickets_list(c: Ctx) -> None:
    body = expect(c.client.get("/api/v1/tickets", params={"limit": 500}))
    ids = [t["ticket_id"] for t in body["tickets"]]
    assert need(c, "ticket_id") in ids, f"ticket not in the {len(ids)} tickets returned"


@check("GET /api/v1/tickets/{id} returns no phone number or transcript")
def _ticket_get(c: Ctx) -> None:
    ticket = expect(c.client.get(f"/api/v1/tickets/{need(c, 'ticket_id')}"))
    assert ticket["interaction_id"] == need(c, "complaint_iid"), ticket
    assert "ani" not in ticket and "transcript" not in ticket, "ticket holds personal data"


@check("GET /api/v1/tickets/{unknown} returns 404")
def _ticket_404(c: Ctx) -> None:
    expect(c.client.get("/api/v1/tickets/BKK-1999-9999"), 404)


@check("PATCH /api/v1/tickets/{id}/status updates the status")
def _ticket_status(c: Ctx) -> None:
    ticket = expect(
        c.client.patch(f"/api/v1/tickets/{need(c, 'ticket_id')}/status", json={"status": "กำลังดำเนินการ"})
    )
    assert ticket["status"] == "กำลังดำเนินการ", ticket


@check("PATCH status rejects an unknown status with 422")
def _ticket_status_bad(c: Ctx) -> None:
    expect(c.client.patch(f"/api/v1/tickets/{need(c, 'ticket_id')}/status", json={"status": "มั่ว"}), 422)


@check("POST /api/v1/tickets/{id}/dispatch is idempotent")
def _dispatch(c: Ctx) -> None:
    url = f"/api/v1/tickets/{need(c, 'ticket_id')}/dispatch"
    first = expect(c.client.post(url, json={}))
    assert first["success"] is True and first["ticket"]["dispatched"] is True, first
    second = expect(c.client.post(url, json={}))
    assert second["ticket"]["dispatched_at"] == first["ticket"]["dispatched_at"], "dispatched_at changed on repeat"


# --------------------------------------------------------- live call gateway
@check("POST /api/v1/calls/{id}/segments accepts partial and final text")
def _segments(c: Ctx) -> None:
    iid = c.state["live_iid"] = c.new_id("LIVE")
    partial = expect(c.client.post(f"/api/v1/calls/{iid}/segments", json={"text": "แถวซอย", "is_final": False}))
    assert partial["success"] is True and partial["segment"]["is_final"] is False, partial
    final = expect(c.client.post(f"/api/v1/calls/{iid}/segments", json={"text": "สุขุมวิท 50 มีท่อแตก"}))
    assert final["segment"]["is_final"] is True, final


@check("POST /api/v1/calls/{id}/end ends the call, and a second end reports no session")
def _end(c: Ctx) -> None:
    iid = need(c, "live_iid")
    first = expect(c.client.post(f"/api/v1/calls/{iid}/end"))
    assert first["had_session"] is True, first
    second = expect(c.client.post(f"/api/v1/calls/{iid}/end"))
    assert second["had_session"] is False, second


# -------------------------------------------------------- voicebot, TTS, outbound
@check("POST /api/v1/voicebot/converse answers in Thai")
def _voicebot_th(c: Ctx) -> None:
    body = expect(
        c.client.post(
            "/api/v1/voicebot/converse", json={"message": "วันเสาร์เขตเปิดทำบัตรประชาชนไหม", "language": "th"}
        )
    )
    assert body["success"] is True and body["reply_text"], body
    assert body["tts_audio_url"].startswith("/api/v1/tts/"), body


@check("POST /api/v1/voicebot/converse answers in English")
def _voicebot_en(c: Ctx) -> None:
    body = expect(
        c.client.post(
            "/api/v1/voicebot/converse", json={"message": "Where can I renew my ID card?", "language": "en"}
        )
    )
    assert body["success"] is True and body["reply_text"], body


@check("GET /api/v1/tts/synthesize returns audio/mpeg")
def _tts(c: Ctx) -> None:
    if c.skip_tts:
        raise Skip("--skip-tts")
    response = c.client.get("/api/v1/tts/synthesize", params={"text": "ทดสอบ", "lang": "th"}, timeout=30)
    assert response.status_code == 200, f"HTTP {response.status_code}: {response.text[:200]}"
    assert response.headers.get("content-type", "").startswith("audio/mpeg"), response.headers
    assert len(response.content) > 1000, f"only {len(response.content)} bytes of audio"


@check("POST /api/v1/outbound/call-citizen returns a script (stub, no real call)")
def _outbound(c: Ctx) -> None:
    body = expect(
        c.client.post(
            "/api/v1/outbound/call-citizen",
            json={
                "phone_number": "0812345678",
                "ticket_id": need(c, "ticket_id"),
                "resolution_summary": "ซ่อมท่อ",
                "district": "คลองเตย",
                "language": "th",
            },
        )
    )
    assert body["status"] == "outbound_call_queued", body
    assert "คลองเตย" in body["spoken_script"], body


# --------------------------------------------------------------- WebSockets
@check("WS /ws/agent/{id}: connected, snapshot, ping, widget actions")
def _ws_agent(c: Ctx) -> None:
    iid = need(c, "complaint_iid")
    ticket_id = need(c, "ticket_id")
    with ws_connect(f"{c.ws_base}/ws/agent/{iid}", open_timeout=10) as ws:
        recv_until(ws, "connected", iid)
        snapshot = recv_until(ws, "snapshot", iid)["data"]
        assert snapshot.get("ticket") and snapshot["ticket"]["ticket_id"] == ticket_id, snapshot
        ws.send(json.dumps({"action": "ping"}))
        recv_until(ws, "pong", iid)
        ws.send(json.dumps({"action": "set_status", "ticket_id": ticket_id, "status": "รับเรื่องแล้ว"}))
        assert recv_until(ws, "ticket", iid)["data"]["status"] == "รับเรื่องแล้ว"
        ws.send(json.dumps({"action": "dispatch", "ticket_id": ticket_id}))
        recv_until(ws, "dispatch_result", iid)
        ws.send("not json")
        recv_until(ws, "error", iid)


@check("WS /ws/agent/{id}: a live transcript segment reaches the widget")
def _ws_live(c: Ctx) -> None:
    iid = c.new_id("WS")
    with ws_connect(f"{c.ws_base}/ws/agent/{iid}", open_timeout=10) as ws:
        recv_until(ws, "connected", iid)
        expect(c.client.post(f"/api/v1/calls/{iid}/segments", json={"text": "แถวซอยสุขุมวิท 50 มีท่อระบายน้ำแตก"}))
        event = recv_until(ws, "transcript", iid)
        assert "สุขุมวิท" in event["data"]["text"], event
    expect(c.client.post(f"/api/v1/calls/{iid}/end"))


@check("WS /ws/monitor: receives events from every call")
def _ws_monitor(c: Ctx) -> None:
    iid = c.new_id("MON")
    with ws_connect(f"{c.ws_base}/ws/monitor", open_timeout=10) as ws:
        recv_until(ws, "connected")
        expect(c.client.post(f"/api/v1/calls/{iid}/segments", json={"text": "ทดสอบมอนิเตอร์"}))
        recv_until(ws, "transcript", iid)
    expect(c.client.post(f"/api/v1/calls/{iid}/end"))


# ------------------------------------------------------------------ runner
def main() -> int:
    parser = argparse.ArgumentParser(description="Live smoke test for the BKK CivicVoice API.")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="API base URL (default: %(default)s)")
    parser.add_argument("--skip-tts", action="store_true", help="skip TTS (edge-tts needs internet access)")
    parser.add_argument("--skip-llm", action="store_true", help="skip the vLLM reachability check")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    ws_base = base.replace("https://", "wss://", 1).replace("http://", "ws://", 1)

    with httpx.Client(base_url=base, timeout=20) as client:
        try:
            client.get("/api/v1/health")
        except httpx.HTTPError as exc:
            print(f"Cannot reach {base} ({exc}). Start the server first.")
            return 2

        ctx = Ctx(client=client, ws_base=ws_base, skip_tts=args.skip_tts, skip_llm=args.skip_llm)
        passed = failed = skipped = 0
        for name, test in TESTS:
            try:
                test(ctx)
            except Skip as exc:
                skipped += 1
                print(f"[SKIP] {name}: {exc}")
                continue
            except Exception as exc:  # keep going, so one failure doesn't hide the others
                failed += 1
                print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
                continue
            passed += 1
            print(f"[PASS] {name}")

    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
