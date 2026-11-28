import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sms_evidence import PROVIDER_URL, SMSKUB_URL, create_app


TICKET_ID = "BKK-2026-0012"
MAP_URL = "https://www.google.com/maps/search/?api=1&query=13.70%2C100.59"
TRACKING = {
    "ticket_id": TICKET_ID, "status": "received", "district": "ดินแดง",
    "location_detail": "ถนนประชาสงเคราะห์",
    "summary_lines": ["ไฟถนนดับ https://unapproved.example/path", "ตรวจสอบไฟส่องสว่าง"],
}
CONFIRMATION = {
    "message": "ไฟถนนดับ เขตคลองเตย",
    "language": "th",
    "interaction_id": "WEB-4c4b8c59-b787-4fec-ba29-6ee7c54f113c",
}
ADMIN = {"Authorization": "Bearer fixture-admin-token"}


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def link_token(link):
    return parse_qs(urlsplit(link).fragment)["token"][0]


class SMSEvidenceTest(unittest.TestCase):
    def setUp(self):
        work = self.enterContext(tempfile.TemporaryDirectory())
        self.env = {"SMS_MODE": "mock", "SMS_DB_PATH": str(Path(work) / "test.sqlite3"),
                    "SMS_ADMIN_TOKEN": "fixture-admin-token"}
        self.provider_requests = []
        self.ticket_id = TICKET_ID
        self.provider_status = 201
        self.smskub_response = {"code": 200, "data": {"total": 1, "block": 0, "send": 1}}
        self.ticket_fetch_status = 200
        self.expected_confirmation = CONFIRMATION

    def fake_upstream(self, request):
        if str(request.url) == PROVIDER_URL:
            self.provider_requests.append(request)
            return httpx.Response(self.provider_status, json={"phone_number_list": [{"message_id": "fixture-1"}]})
        if str(request.url) == SMSKUB_URL:
            self.provider_requests.append(request)
            return httpx.Response(200, json=self.smskub_response)
        if request.method == "GET":
            self.assertEqual(request.url.path, f"/api/v1/tickets/{TICKET_ID}")
            return httpx.Response(self.ticket_fetch_status, json={**TRACKING, "internal": "hidden"})
        self.assertEqual(request.url.path, "/api/v1/voicebot/converse")
        self.assertEqual(json.loads(request.content), self.expected_confirmation)
        return httpx.Response(200, json={"success": True, "ticket_id": self.ticket_id})

    def client(self):
        app = create_app(self.env, httpx.MockTransport(self.fake_upstream))
        return self.enterContext(TestClient(app, base_url="http://127.0.0.1:8766"))

    def enable_provider(self):
        self.env.update(SMS_MODE="thaibulksms", SMS_PUBLIC_ORIGIN="https://civic.example.test",
                        THAIBULKSMS_API_KEY="fixture-key", THAIBULKSMS_API_SECRET="fixture-secret",
                        THAIBULKSMS_SENDER="Fixture", SMS_ALLOWED_RECIPIENTS="0812345678",
                        SMS_CONFIRM_SECRET="fixture-gateway-secret")

    def smskub_grant(self):
        self.env.update(SMS_MODE="smskub", SMS_PUBLIC_ORIGIN="https://civic.example.test",
                        SMSKUB_API_KEY="fixture-key", SMSKUB_SENDER="Fixture",
                        SMS_ALLOWED_RECIPIENTS="0812345678", SMS_CONFIRM_SECRET="fixture-gateway-secret")
        client = self.client()
        self.assertEqual(client.get("/api/sms/health").json(),
                         {"ready": True, "mode": "smskub", "requires_gateway": True})
        confirm = client.post("/api/sms/confirm", json=CONFIRMATION,
                              headers={"X-SMS-Confirm-Secret": "fixture-gateway-secret"})
        return client, bearer(confirm.json()["sms_grant"])

    def test_smskub_sends_api_key_and_json_and_accepts_one_unblocked_recipient(self):
        client, grant = self.smskub_grant()
        response = client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"})
        self.assertEqual(response.json(), {"status": "accepted", "provider_message_id": None})
        request, = self.provider_requests
        self.assertEqual(request.headers["key"], "fixture-key")
        sent = json.loads(request.content)
        self.assertEqual(sent["from"], "Fixture")
        self.assertEqual(sent["to"], ["66812345678"])
        self.assertIn(f"{TICKET_ID}\nไฟถนนดับ\nถนนประชาสงเคราะห์ เขตดินแดง", sent["message"])
        self.assertNotIn("unapproved.example", sent["message"])
        link = sent["message"].split()[-1]
        self.assertEqual(client.get("/api/sms/evidence", headers=bearer(link_token(link))).json()["ticket_id"], TICKET_ID)

    def test_smskub_rejects_blocked_recipient_even_on_http_200(self):
        self.smskub_response = {"code": 200, "data": {"total": 1, "block": 1, "send": 0}}
        client, grant = self.smskub_grant()
        response = client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("ผู้ให้บริการไม่รับ SMS", response.json()["detail"])

    def test_smskub_checks_application_error_even_on_http_200(self):
        self.smskub_response = {"code": 500, "error": "balance is not enough"}
        client, grant = self.smskub_grant()
        response = client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("ผู้ให้บริการไม่รับ SMS", response.json()["detail"])
        self.assertEqual(client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"}).status_code, 409)
        self.assertEqual(len(self.provider_requests), 1)

    def test_mock_link_saves_evidence_for_confirmed_ticket(self):
        client = self.client()
        self.expected_confirmation = {**CONFIRMATION, "reviewed_location": {
            "district": "ดินแดง", "location_detail": "ถนนประชาสงเคราะห์",
        }}
        confirm = client.post("/api/sms/confirm", json=self.expected_confirmation,
                              headers={"Origin": "http://localhost:8765"})
        grant = bearer(confirm.json()["sms_grant"])
        sent = client.post("/api/sms/send", headers=grant, json={"phone": "081-234-5678"})
        self.assertEqual(sent.json()["status"], "mock")
        self.assertIn("ไฟถนนดับ", sent.json()["preview"])
        self.assertEqual(self.provider_requests, [])
        self.assertEqual(client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"}).status_code, 409)
        access = bearer(link_token(sent.json()["evidence_url"]))
        self.assertEqual(client.get("/api/sms/evidence", headers=grant).status_code, 404)
        self.assertEqual(client.put("/api/sms/evidence/location", headers=access,
                                    json={"latitude": 13.70, "longitude": 100.59}).json()["ticket_id"], TICKET_ID)
        map_endpoint = "/api/sms/evidence/map-link"
        self.assertEqual(client.put(map_endpoint, json={"map_url": MAP_URL}).status_code, 401)
        self.assertEqual(client.put(map_endpoint, headers=access,
                                    json={"map_url": "https://www.google.com.example/maps/"}).status_code, 422)
        self.assertEqual(client.put(map_endpoint, headers=access, json={"map_url": MAP_URL}).json()["map_url"], MAP_URL)
        self.assertEqual(client.put("/api/sms/evidence/photo", headers=access, content=b"bad image").status_code, 422)
        image = io.BytesIO()
        Image.new("RGB", (2, 2)).save(image, format="PNG")
        saved = client.put("/api/sms/evidence/photo", headers=access, content=image.getvalue())
        self.assertEqual(saved.json()["has_photo"], 1)
        retrieved = client.get("/api/sms/evidence", headers=access).json()
        self.assertEqual(retrieved["latitude"], 13.70)
        self.assertEqual(retrieved["tracking"], TRACKING)
        self.assertEqual(retrieved["map_url"], MAP_URL)
        admin_url = f"/api/sms/admin/evidence/{TICKET_ID}/photo"
        self.assertEqual(client.get(f"/api/sms/admin/evidence/{TICKET_ID}", headers=ADMIN).json()["map_url"], MAP_URL)
        self.assertEqual(client.get(admin_url, headers=access).status_code, 401)
        self.assertEqual(client.get(admin_url, headers=ADMIN).content, image.getvalue())

    def test_no_grant_when_voicebot_has_not_created_ticket(self):
        self.ticket_id = None
        self.env["SMS_MODE"] = "mock"
        client = self.client()
        confirm = client.post("/api/sms/confirm", json=CONFIRMATION, headers={"Origin": "http://localhost:8765"})
        self.assertEqual(confirm.status_code, 200)
        self.assertNotIn("sms_grant", confirm.json())
        self.assertEqual(client.post("/api/sms/send", json={"phone": "0812345678"}).status_code, 401)

    def test_unavailable_ticket_can_be_retried_before_contacting_provider(self):
        client, grant = self.smskub_grant()
        self.ticket_fetch_status = 503
        self.assertEqual(client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"}).status_code, 424)
        self.assertEqual(self.provider_requests, [])
        self.ticket_fetch_status = 200
        self.assertEqual(client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"}).json()["status"],
                         "accepted")

    def test_real_mode_requires_gateway_and_sends_one_request_to_provider(self):
        self.enable_provider()
        client = self.client()
        self.assertEqual(client.post("/api/sms/confirm", json=CONFIRMATION,
                                     headers={"Origin": "http://localhost:8765"}).status_code, 403)
        confirm = client.post("/api/sms/confirm", json=CONFIRMATION,
                              headers={"X-SMS-Confirm-Secret": "fixture-gateway-secret"})
        grant = bearer(confirm.json()["sms_grant"])
        self.assertEqual(client.post("/api/sms/send", headers=grant, json={"phone": "0890000000"}).status_code, 403)
        accepted = client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"})
        self.assertEqual(accepted.json(), {"status": "accepted", "provider_message_id": "fixture-1"})
        self.assertEqual(client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"}).status_code, 409)
        self.assertEqual(len(self.provider_requests), 1)
        request = self.provider_requests[0]
        self.assertTrue(request.headers["Authorization"].startswith("Basic "))
        form = parse_qs(request.content.decode())
        self.assertEqual(form["sender"], ["Fixture"])
        self.assertEqual(form["msisdn"], ["+66812345678"])
        link = form["message"][0].split()[-1]
        self.assertEqual(urlsplit(link).hostname, "civic.example.test")
        self.assertEqual(client.get("/api/sms/evidence", headers=bearer(link_token(link))).json()["ticket_id"], TICKET_ID)

    def test_ambiguous_provider_failure_does_not_send_again(self):
        self.enable_provider()
        self.provider_status = 503
        client = self.client()
        confirm = client.post("/api/sms/confirm", json=CONFIRMATION,
                              headers={"X-SMS-Confirm-Secret": "fixture-gateway-secret"})
        grant = bearer(confirm.json()["sms_grant"])
        self.assertEqual(client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"}).status_code, 502)
        self.assertEqual(client.post("/api/sms/send", headers=grant, json={"phone": "0812345678"}).status_code, 409)
        self.assertEqual(len(self.provider_requests), 1)
