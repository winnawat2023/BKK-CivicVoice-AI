"""Tests that pin the backend to the written specs (.kiro/specs/bkk-civic-connect/*.md).

Each test names the requirement it proves; see the traceability matrix in
aidlc/spaces/default/knowledge/aidlc-shared/ai-engine-traceability.md.
"""

from __future__ import annotations

import re
import time

from tests.conftest import FLOOD_TEXT, ID_CARD_TEXT
from tests.test_api import drain_until, webhook

ARI_TEXT = "แจ้งทางเท้าชำรุด มีกระเบื้องแตกหน้าร้านสะดวกซื้อ ปากซอยอารีย์ คนสะดุดล้มบ่อยครับ"  # PRD §6 demo script
US2_TEXT = "ท่อระบายน้ำแตก น้ำท่วมซอยสุขุมวิท 50 อันตรายมาก"  # PRD user story 2


# --------------------------------------------------------------- design.md §3.1
def test_design_3_1_webhook_accepts_the_documented_payload(client):
    r = client.post(
        "/api/v1/genesys/webhook",
        json={
            "interaction_id": "SPEC-1",
            "ani": "0812345678",
            "channel": "chat",
            "text_or_audio_stream": FLOOD_TEXT,
            "timestamp": "2026-11-30T10:00:00+07:00",
        },
    )
    assert r.status_code == 200
    assert r.json()["next_action"] == "ticket_created"


def test_prd_voice_webhook_alias_still_works(client):
    r = client.post("/api/v1/voice/webhook", json={"interaction_id": "SPEC-2", "transcript": FLOOD_TEXT})
    assert r.status_code == 200 and r.json()["ticket_id"]


# --------------------------------------------------------------- design.md §3.2
def test_design_3_2_classify_returns_the_documented_fields(client):
    body = client.post("/api/v1/civic/classify", json={"text": FLOOD_TEXT}).json()
    for key in ("intent", "category", "district", "location_detail", "urgency", "summary_th", "suggested_action"):
        assert key in body, key
    assert body["intent"] in ("complaint", "inquiry")
    assert body["category"] in ("ถนน", "ทางเท้า", "ผิดกฎจราจร", "ไฟฟ้า", "ความสะอาด", "อื่นๆ")
    assert body["urgency"] in ("low", "medium", "high")
    assert body["summary_th"] and body["suggested_action"]


# ------------------------------------------------------------ PRD user story 1
def test_us1_ac3_answer_from_regulations_within_two_seconds(client):
    started = time.perf_counter()
    body = client.post("/api/v1/civic/ask", json={"text": ID_CARD_TEXT}).json()
    assert time.perf_counter() - started < 2.0
    assert body["answered"] and "08:30" in body["answer"] and body["sources"]


# ------------------------------------------------------------ PRD user story 2
def test_us2_ac2_ac3_entities_and_ticket_id(client):
    r = webhook(client, "SPEC-US2", US2_TEXT).json()
    a = r["analysis"]
    assert (a["category"], a["sub_category"]) == ("อื่นๆ", "ท่อระบายน้ำ/น้ำท่วม")
    assert a["district"] == "คลองเตย" and "สุขุมวิท 50" in a["location_detail"]
    assert a["urgency"] == "high"
    assert re.fullmatch(r"BKK-\d{4}-\d{4}", r["ticket_id"])
    assert "ท่อระบายน้ำ" in r["reply_text"]  # spoken confirmation


def test_prd_demo_script_sidewalk_at_ari_goes_to_phaya_thai(client):
    r = webhook(client, "SPEC-DEMO", ARI_TEXT).json()
    a = r["analysis"]
    assert (a["category"], a["district"]) == ("ทางเท้า", "พญาไท")
    assert r["ticket_id"]


# ------------------------------------------------------------ PRD user story 3
def test_us3_widget_gets_transcript_three_point_summary_and_action(client):
    with client.websocket_connect("/ws/agent/SPEC-US3") as ws:
        ws.receive_json(), ws.receive_json()
        webhook(client, "SPEC-US3", FLOOD_TEXT)
        transcript, _ = drain_until(ws, "transcript")
        assert transcript["data"]["text"] == FLOOD_TEXT  # AC1: live transcript
        summary, _ = drain_until(ws, "summary")
        assert len(summary["data"]["summary_lines"]) == 3  # AC2: 3 key points
        assert summary["data"]["suggested_action"] and summary["data"]["target_unit"]  # AC3


def test_design_3_3_widget_create_ticket_button(client):
    """One-click "Create Ticket": the call is routed to an agent, no ticket exists yet."""
    iid = "SPEC-BTN"
    with client.websocket_connect(f"/ws/agent/{iid}") as ws:
        ws.receive_json(), ws.receive_json()
        client.post(f"/api/v1/calls/{iid}/segments", json={"text": FLOOD_TEXT})
        drain_until(ws, "summary")
        assert client.get("/api/v1/tickets").json()["total"] == 0  # live analysis alone files nothing
        ws.send_json({"action": "create_ticket"})
        result, seen = drain_until(ws, "ticket_result", limit=20)
        assert result["data"]["success"] and result["data"]["created"]
        assert any(m["event"] == "ticket" for m in seen)
        ws.send_json({"action": "create_ticket"})  # pressing twice never makes a second ticket
        again, _ = drain_until(ws, "ticket_result", limit=20)
        assert again["data"]["success"] and not again["data"]["created"]
    assert client.get("/api/v1/tickets").json()["total"] == 1


def test_design_3_3_create_ticket_refused_when_nothing_understood(client):
    iid = "SPEC-NOTHING"
    with client.websocket_connect(f"/ws/agent/{iid}") as ws:
        ws.receive_json(), ws.receive_json()
        ws.send_json({"action": "create_ticket"})
        result, _ = drain_until(ws, "ticket_result")
        assert result["data"]["success"] is False
    assert client.get("/api/v1/tickets").json()["total"] == 0


def test_design_3_3_forward_to_district_office(client):
    webhook(client, "SPEC-FWD", FLOOD_TEXT)
    with client.websocket_connect("/ws/agent/SPEC-FWD") as ws:
        ws.receive_json(), ws.receive_json()
        ws.send_json({"action": "dispatch"})
        result, _ = drain_until(ws, "dispatch_result")
        assert result["data"]["success"] and "คลองเตย" in result["data"]["message"]
