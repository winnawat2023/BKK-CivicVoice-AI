"""End-to-end API tests: Genesys webhook -> AI -> ticket -> WebSocket events for the widget."""

from __future__ import annotations

import datetime as dt

from tests.conftest import FLOOD_TEXT, ID_CARD_TEXT, base_settings, fake_llm_transport

YEAR = dt.date.today().year


def drain_until(ws, event: str, limit: int = 12):
    """Read frames until `event` arrives; returns (that frame, all frames seen)."""
    seen = []
    for _ in range(limit):
        msg = ws.receive_json()
        seen.append(msg)
        if msg["event"] == event:
            return msg, seen
    raise AssertionError(f"{event} not received, got {[m['event'] for m in seen]}")


def webhook(client, iid="CALL-1", transcript=FLOOD_TEXT, ani="0812345678"):
    return client.post("/api/v1/genesys/webhook", json={"interaction_id": iid, "ani": ani, "transcript": transcript})


# --------------------------------------------------------------- basics
def test_health_endpoints(client):
    assert client.get("/").json()["status"] == "online"
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok" and body["tickets"] == 0


def test_health_can_probe_llm(make_client):
    c = make_client(base_settings(llm_enabled=True), fake_llm_transport())
    body = c.get("/api/v1/health", params={"check_llm": True}).json()
    assert body["llm"]["reachable"] and body["llm"]["models"] == ["typhoon-8b"]


def test_classify_endpoint(client):
    body = client.post("/api/v1/civic/classify", json={"text": FLOOD_TEXT}).json()
    assert body["intent"] == "complaint" and body["district"] == "คลองเตย" and body["urgency"] == "high"
    assert len(body["summary_lines"]) == 3


def test_ask_endpoint_answers_and_declines(client):
    ok = client.post("/api/v1/civic/ask", json={"text": "เบี้ยยังชีพผู้สูงอายุ 80 ปีได้เดือนละเท่าไหร่"}).json()
    assert ok["answered"] and "800" in ok["answer"]
    no = client.post("/api/v1/civic/ask", json={"text": "ขอใบอนุญาตก่อสร้างอาคารสูง"}).json()
    assert not no["answered"] and no["transfer_to_agent"]


def test_webhook_validation(client):
    assert client.post("/api/v1/genesys/webhook", json={"ani": "0812345678"}).status_code == 422  # no interaction_id


def test_webhook_call_start_without_speech_waits_for_first_utterance(client):
    """Data Action may send only ID + ANI at call start: accepted, no reply, no ticket yet."""
    r = client.post("/api/v1/genesys/webhook", json={"interaction_id": "START-1", "ani": "0812345678"})
    assert r.status_code == 200
    body = r.json()
    assert body["next_action"] == "await_speech" and body["reply_text"] == "" and body["ticket_id"] is None
    assert client.get("/api/v1/tickets").json()["total"] == 0

    speech = webhook(client, iid="START-1", transcript=FLOOD_TEXT).json()
    assert speech["next_action"] == "ticket_created" and speech["ticket_id"]


def test_webhook_empty_transcript_is_treated_as_no_speech(client):
    body = client.post("/api/v1/genesys/webhook", json={"interaction_id": "EMPTY-1", "transcript": "  "}).json()
    assert body["next_action"] == "await_speech"


# ------------------------------------------------------ webhook: complaint
def test_webhook_complaint_creates_ticket(client):
    r = webhook(client).json()
    assert r["success"] and r["next_action"] == "ticket_created"
    assert r["ticket_id"] == f"BKK-{YEAR}-0001"
    assert r["analysis"]["district"] == "คลองเตย"
    assert r["analysis"]["sub_category"] == "ท่อระบายน้ำ/น้ำท่วม"
    assert r["analysis"]["urgency"] == "high"
    assert r["ticket_id"].replace("-", " ") in r["reply_text"]
    assert r["tts_audio_url"].startswith("/api/v1/tts/synthesize?text=")

    tickets = client.get("/api/v1/tickets").json()
    assert tickets["total"] == 1
    stored = tickets["tickets"][0]
    assert "transcript" not in stored and "caller_ani" not in stored
    assert "0812345678" not in str(stored) and FLOOD_TEXT not in str(stored)


def test_same_call_never_creates_two_tickets(client):
    first = webhook(client).json()
    again = webhook(client).json()
    assert first["ticket_id"] == again["ticket_id"] and again["duplicate"] is True
    assert client.get("/api/v1/tickets").json()["total"] == 1


def test_complaint_without_location_asks_once_then_creates_ticket(client):
    first = webhook(client, "CALL-L", "ท่อน้ำแตกน้ำท่วมถนนช่วยด้วย").json()
    assert first["next_action"] == "ask_location" and first["ticket_id"] is None
    second = webhook(client, "CALL-L", "ท่อน้ำแตกน้ำท่วมถนนช่วยด้วยครับ ไม่รู้ว่าที่ไหน").json()
    assert second["next_action"] == "ticket_created" and second["ticket_id"]
    assert second["analysis"]["needs_location"] is True


def test_location_given_in_second_turn_is_used(client):
    webhook(client, "CALL-L2", "ท่อน้ำแตกน้ำท่วมถนนช่วยด้วย")
    second = webhook(client, "CALL-L2", "ซอยอารีย์ เขตพญาไท").json()
    assert second["next_action"] == "ticket_created"
    assert second["analysis"]["district"] == "พญาไท"


# --------------------------------------------------------- webhook: inquiry
def test_webhook_inquiry_is_answered_without_ticket(client):
    r = webhook(client, "CALL-Q", ID_CARD_TEXT).json()
    assert r["next_action"] == "answer" and r["ticket_id"] is None
    assert r["analysis"]["intent"] == "inquiry" and r["answer"]["answered"]
    assert "08:30" in r["reply_text"]
    assert client.get("/api/v1/tickets").json()["total"] == 0


def test_inquiry_out_of_dataset_offers_transfer(client):
    r = webhook(client, "CALL-Q2", "สอบถามขั้นตอนขอใบอนุญาตก่อสร้างอาคารสูงหน่อยครับ").json()
    assert r["next_action"] == "transfer_to_agent" and not r["answer"]["answered"]


# ---------------------------------------------------- webhook: not understood
def test_unclear_speech_is_asked_twice_then_transferred(client):
    actions = [webhook(client, "CALL-U", "อืม...").json()["next_action"] for _ in range(3)]
    assert actions == ["ask_repeat", "ask_repeat", "transfer_to_agent"]
    assert client.get("/api/v1/tickets").json()["total"] == 0


# ---------------------------------------------------------------- tickets
def test_ticket_endpoints(client):
    tid = webhook(client).json()["ticket_id"]
    assert client.get(f"/api/v1/tickets/{tid}").json()["district"] == "คลองเตย"
    assert client.get("/api/v1/tickets/BKK-0000-0000").status_code == 404

    patched = client.patch(f"/api/v1/tickets/{tid}/status", json={"status": "แก้ไขเสร็จ"})
    assert patched.status_code == 200 and patched.json()["status"] == "แก้ไขเสร็จ"
    assert client.patch(f"/api/v1/tickets/{tid}/status", json={"status": "มั่ว"}).status_code == 422
    assert client.patch("/api/v1/tickets/BKK-0000-0000/status", json={"status": "แก้ไขเสร็จ"}).status_code == 404

    assert client.get("/api/v1/tickets", params={"status": "แก้ไขเสร็จ"}).json()["total"] == 1
    assert client.get("/api/v1/tickets", params={"status": "รับเรื่องแล้ว"}).json()["total"] == 0
    assert client.get("/api/v1/tickets", params={"status": "มั่ว"}).status_code == 422
    assert client.get("/api/v1/tickets", params={"district": "บางรัก"}).json()["total"] == 0


def test_rest_dispatch(client):
    tid = webhook(client).json()["ticket_id"]
    res = client.post(f"/api/v1/tickets/{tid}/dispatch").json()
    assert res["success"] and res["ticket"]["dispatched"]
    assert client.post("/api/v1/tickets/BKK-0000-0000/dispatch").status_code == 404


# --------------------------------------------------------------- websocket
def test_widget_receives_live_events_from_webhook(client):
    with client.websocket_connect("/ws/agent/CALL-W") as ws:
        assert ws.receive_json()["event"] == "connected"
        snap = ws.receive_json()
        assert snap["event"] == "snapshot" and snap["data"]["transcript"] == []

        webhook(client, "CALL-W")
        transcript = ws.receive_json()
        assert transcript["event"] == "transcript"
        assert transcript["data"]["text"] == FLOOD_TEXT and transcript["data"]["speaker"] == "caller"
        assert transcript["data"]["caller_ani"] == "0812345678"

        summary = ws.receive_json()
        assert summary["event"] == "summary" and summary["interaction_id"] == "CALL-W"
        d = summary["data"]
        assert len(d["summary_lines"]) == 3
        assert d["district"] == "คลองเตย" and d["urgency"] == "high" and d["sla_days"] == 1
        assert d["ticket_id"] == f"BKK-{YEAR}-0001"

        ticket = ws.receive_json()
        assert ticket["event"] == "ticket" and ticket["data"]["ticket_id"] == d["ticket_id"]

        legacy = ws.receive_json()  # what the first widget version reads
        assert legacy["event"] == "live_update"
        for key in ("transcript", "caller_ani", "category", "summary", "district", "urgency", "sla_days"):
            assert key in legacy["data"]
        assert legacy["data"]["category"] == "ท่อระบายน้ำ/น้ำท่วม"


def test_live_segments_reach_widget_and_trigger_summary(client):
    with client.websocket_connect("/ws/agent/CALL-S") as ws:
        ws.receive_json(), ws.receive_json()  # connected, snapshot
        r = client.post(
            "/api/v1/calls/CALL-S/segments",
            json={"text": "ขยะล้นหน้าตลาด", "speaker": "caller", "is_final": False, "ani": "0899999999"},
        )
        assert r.json()["widgets"] == 1
        partial = ws.receive_json()
        assert partial["event"] == "transcript" and partial["data"]["is_final"] is False

        client.post("/api/v1/calls/CALL-S/segments", json={"text": "ขยะล้นหน้าตลาดบางรัก เหม็นมาก", "is_final": True})
        final, _ = drain_until(ws, "transcript")
        assert final["data"]["is_final"] is True
        summary, _ = drain_until(ws, "summary")
        assert summary["data"]["category"] == "ความสะอาด"
        assert summary["data"]["ticket_id"] is None  # live analysis never files a ticket

    assert client.get("/api/v1/tickets").json()["total"] == 0


def test_partial_segment_is_replaced_not_duplicated(client):
    client.post("/api/v1/calls/CALL-P/segments", json={"text": "ไฟ", "is_final": False})
    client.post("/api/v1/calls/CALL-P/segments", json={"text": "ไฟดับ", "is_final": False})
    client.post("/api/v1/calls/CALL-P/segments", json={"text": "ไฟดับหน้าบ้านครับ", "is_final": True})
    with client.websocket_connect("/ws/agent/CALL-P") as ws:
        ws.receive_json()
        snap = ws.receive_json()["data"]
    assert [s["text"] for s in snap["transcript"]] == ["ไฟดับหน้าบ้านครับ"]


def test_late_joining_widget_gets_snapshot_with_ticket(client):
    webhook(client, "CALL-J")
    with client.websocket_connect("/ws/agent/CALL-J") as ws:
        ws.receive_json()
        snap = ws.receive_json()["data"]
    assert snap["transcript"][0]["text"] == FLOOD_TEXT
    assert snap["summary"]["district"] == "คลองเตย"
    assert snap["ticket"]["ticket_id"] == f"BKK-{YEAR}-0001"
    assert snap["caller_ani"] == "0812345678"


def test_widget_dispatch_button_over_websocket(client):
    webhook(client, "CALL-D")
    with client.websocket_connect("/ws/agent/CALL-D") as ws:
        ws.receive_json(), ws.receive_json()
        ws.send_json({"action": "dispatch"})
        result, _ = drain_until(ws, "dispatch_result")
        assert result["data"]["success"] and result["data"]["ticket"]["dispatched"]
        assert "คลองเตย" in result["data"]["message"]
    assert client.get("/api/v1/tickets").json()["tickets"][0]["status"] == "กำลังดำเนินการ"


def test_widget_dispatch_without_ticket_reports_error(client):
    with client.websocket_connect("/ws/agent/CALL-NOTICKET") as ws:
        ws.receive_json(), ws.receive_json()
        ws.send_json({"action": "dispatch"})
        result, _ = drain_until(ws, "dispatch_result")
        assert result["data"]["success"] is False


def test_widget_ping_status_and_bad_messages(client):
    tid = webhook(client, "CALL-A").json()["ticket_id"]
    with client.websocket_connect("/ws/agent/CALL-A") as ws:
        ws.receive_json(), ws.receive_json()
        ws.send_json({"action": "ping"})
        assert ws.receive_json()["event"] == "pong"
        ws.send_text("not json")
        assert ws.receive_json()["event"] == "error"
        ws.send_json({"action": "teleport"})
        assert ws.receive_json()["event"] == "error"
        ws.send_json({"action": "set_status", "ticket_id": tid, "status": "แก้ไขเสร็จ"})
        ticket, _ = drain_until(ws, "ticket")
        assert ticket["data"]["status"] == "แก้ไขเสร็จ"
        ws.send_json({"action": "set_status", "ticket_id": "BKK-0000-0000", "status": "แก้ไขเสร็จ"})
        assert ws.receive_json()["event"] == "error"


def test_events_only_go_to_the_matching_call_and_monitor(client):
    with client.websocket_connect("/ws/agent/OTHER") as other, client.websocket_connect("/ws/monitor") as mon:
        other.receive_json(), other.receive_json()
        mon.receive_json()  # connected (no snapshot for the monitor)
        webhook(client, "CALL-M")
        seen, _ = drain_until(mon, "summary")
        assert seen["interaction_id"] == "CALL-M"
        other.send_json({"action": "ping"})
        assert other.receive_json()["event"] == "pong"  # nothing else was queued for it


def test_two_widgets_on_the_same_call_both_receive(client):
    with client.websocket_connect("/ws/agent/CALL-2") as a, client.websocket_connect("/ws/agent/CALL-2") as b:
        for w in (a, b):
            w.receive_json(), w.receive_json()
        webhook(client, "CALL-2")
        for w in (a, b):
            assert drain_until(w, "summary")[0]["data"]["district"] == "คลองเตย"


def test_end_call_purges_transcript_and_phone_number(client):
    webhook(client, "CALL-E")
    with client.websocket_connect("/ws/agent/CALL-E") as ws:
        ws.receive_json(), ws.receive_json()
        assert client.post("/api/v1/calls/CALL-E/end").json()["had_session"] is True
        assert drain_until(ws, "call_ended")[0]["data"]["ticket"]["ticket_id"]
    with client.websocket_connect("/ws/agent/CALL-E") as ws:
        ws.receive_json()
        snap = ws.receive_json()["data"]
    assert snap["transcript"] == [] and snap["caller_ani"] == ""
    assert snap["ticket"] is not None  # the ticket itself survives


# --------------------------------------------------------- with a fake LLM
def test_webhook_uses_llm_result_when_available(make_client):
    reply = {
        "intent": "complaint", "category": "อื่นๆ", "sub_category": "ท่อระบายน้ำ/น้ำท่วม",
        "district": "คลองเตย", "location_detail": "ซอยสุขุมวิท 50", "urgency": "high",
        "summary": ["ท่อแตก น้ำท่วม", "ซอยสุขุมวิท 50 เขตคลองเตย", "เร่งด่วนสูง"],
        "confidence": 0.93,
    }
    c = make_client(base_settings(llm_enabled=True), fake_llm_transport(classify=lambda _: reply))
    r = webhook(c).json()
    assert r["analysis"]["engine"] == "llm" and r["analysis"]["summary_lines"][0] == "ท่อแตก น้ำท่วม"


def test_widget_gets_instant_provisional_summary_then_llm_summary(make_client):
    """Slow LLM: the widget must not wait for it (2 s requirement) - provisional first, refined after."""
    reply = {"intent": "complaint", "category": None, "sub": "drain", "district": "คลองเตย",
             "urgency": "high", "topic": None}
    c = make_client(base_settings(llm_enabled=True), fake_llm_transport(classify=lambda _: reply))
    with c.websocket_connect("/ws/agent/CALL-P") as ws:
        ws.receive_json(), ws.receive_json()  # connected, snapshot
        webhook(c, "CALL-P")
        first, seen = drain_until(ws, "summary")
        assert first["data"]["provisional"] is True and first["data"]["engine"] == "rules"
        second = next(m for m in drain_until(ws, "ticket", limit=20)[1] if m["event"] == "summary")
        assert second["data"]["provisional"] is False and second["data"]["engine"] == "llm"


def test_no_provisional_summary_without_llm(client):
    with client.websocket_connect("/ws/agent/CALL-Q") as ws:
        ws.receive_json(), ws.receive_json()
        webhook(client, "CALL-Q")
        msg, _ = drain_until(ws, "summary")
        assert msg["data"]["provisional"] is False


def test_webhook_survives_llm_outage(make_client):
    c = make_client(base_settings(llm_enabled=True), fake_llm_transport(classify=lambda _: 503, rag=lambda _: 503))
    complaint = webhook(c, "CALL-X1").json()
    assert complaint["analysis"]["engine"] == "rules" and complaint["ticket_id"]
    inquiry = webhook(c, "CALL-X2", ID_CARD_TEXT).json()
    assert inquiry["answer"]["via"] == "extractive" and inquiry["reply_text"]


# --------------------------------------------------------------- voicebot
def test_voicebot_converse_inquiry_and_complaint(client):
    q = client.post("/api/v1/voicebot/converse", json={"message": ID_CARD_TEXT}).json()
    assert q["intent"] == "inquiry" and "08:30" in q["reply_text"]
    assert q["tts_audio_url"].startswith("/api/v1/tts/synthesize?text=")

    c = client.post("/api/v1/voicebot/converse", json={"message": FLOOD_TEXT}).json()
    assert c["intent"] == "complaint" and "ท่อระบายน้ำ" in c["reply_text"]
    assert client.get("/api/v1/tickets").json()["total"] == 0  # no interaction_id -> no ticket

    t = client.post("/api/v1/voicebot/converse", json={"message": FLOOD_TEXT, "interaction_id": "V-1"}).json()
    assert t["next_action"] == "ticket_created" and t["ticket_id"]


def test_voicebot_english_falls_back_without_llm(client):
    r = client.post("/api/v1/voicebot/converse", json={"message": "Where can I renew my ID?", "language": "en"}).json()
    assert r["success"] and "1555" in r["reply_text"]


def test_reviewed_location_overrides_transcript_and_is_saved_in_ticket(client):
    districts = client.get("/api/v1/civic/districts").json()["districts"]
    assert len(set(districts)) == 50 and "ดินแดง" in districts
    review = {"district": "ดินแดง", "location_detail": "ถนนประชาสงเคราะห์"}
    request = {"message": FLOOD_TEXT, "interaction_id": "V-review", "reviewed_location": review}
    response = client.post("/api/v1/voicebot/converse", json=request)
    assert response.status_code == 200
    ticket_id = response.json()["ticket_id"]
    ticket = client.get(f"/api/v1/tickets/{ticket_id}").json()
    assert {key: ticket[key] for key in review} == review
    assert "เขตดินแดง" in " ".join(ticket["summary_lines"])
    assert client.post("/api/v1/voicebot/converse", json=request).json()["ticket_id"] == ticket_id
    request["reviewed_location"] = {**review, "district": "พระนคร"}
    assert client.post("/api/v1/voicebot/converse", json=request).status_code == 409


def test_voicebot_rejects_unknown_reviewed_district(client):
    response = client.post("/api/v1/voicebot/converse", json={
        "message": FLOOD_TEXT, "interaction_id": "V-invalid",
        "reviewed_location": {"district": "เขตที่ไม่มีในรายการ"},
    })
    assert response.status_code == 422
    assert client.get("/api/v1/tickets").json()["total"] == 0


def test_outbound_call_script_does_not_log_or_leak_beyond_payload(client):
    r = client.post(
        "/api/v1/outbound/call-citizen",
        json={"phone_number": "0812345678", "ticket_id": "BKK-2026-0001", "resolution_summary": "ซ่อมท่อ", "district": "คลองเตย"},
    ).json()
    assert r["status"] == "outbound_call_queued"
    assert "BKK 2026 0001" in r["spoken_script"] and "คลองเตย" in r["spoken_script"]
    assert "%" in r["tts_preview_url"]  # URL-encoded Thai text
