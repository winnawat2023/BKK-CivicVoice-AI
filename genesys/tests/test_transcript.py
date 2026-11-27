import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.config import Settings
from app.transcript import build_turn_payload, emit_turn


class _WebhookHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):  # noqa: N802 - stdlib signature
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.__class__.received.append(
            {
                "path": self.path,
                "headers": dict(self.headers.items()),
                "json": json.loads(body.decode("utf-8")),
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format, *args):  # noqa: A002
        return


@pytest.fixture
def webhook_server():
    _WebhookHandler.received = []
    server = HTTPServer(("127.0.0.1", 0), _WebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.asyncio
async def test_emit_turn_posts_payload(webhook_server):
    port = webhook_server.server_port
    settings = Settings(
        _env_file=None,
        transcript_webhook_url=f"http://127.0.0.1:{port}/hook",
        transcript_webhook_bearer_token="secret-token",
    )

    await emit_turn(
        settings,
        {
            "interaction_id": "c1",
            "ani": "0847685368",
            "dnis": "02-096-6763",
            "channel": "voice",
            "role": "caller",
            "transcript": "สวัสดี",
        },
    )

    assert len(_WebhookHandler.received) == 1
    req = _WebhookHandler.received[0]
    assert req["path"] == "/hook"
    assert req["headers"].get("Authorization") == "Bearer secret-token"
    body = req["json"]
    assert body["interaction_id"] == "c1"
    assert body["ani"] == "0847685368"
    assert body["dnis"] == "02-096-6763"
    assert body["channel"] == "voice"
    assert body["role"] == "caller"
    assert body["transcript"] == "สวัสดี"
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_emit_turn_maps_to_live_civic_segments(webhook_server):
    settings = Settings(
        _env_file=None,
        transcript_webhook_format="civic_segments",
        transcript_webhook_url=f"http://127.0.0.1:{webhook_server.server_port}/api/v1/calls/{{interaction_id}}/segments",
    )
    await emit_turn(settings, {"interaction_id": "conv 1", "ani": "081", "role": "bot", "transcript": "รับทราบ"})
    request = _WebhookHandler.received[0]
    assert request["path"] == "/api/v1/calls/conv%201/segments"
    assert request["json"] == {"speaker": "bot", "text": "รับทราบ", "is_final": True, "ani": "081"}


@pytest.mark.asyncio
async def test_emit_turn_noop_without_url():
    settings = Settings(transcript_webhook_url="")
    await emit_turn(settings, {"role": "bot", "text": "hi"})


@pytest.mark.asyncio
async def test_emit_turn_failure_is_swallowed():
    settings = Settings(
        transcript_webhook_url="http://127.0.0.1:9/unreachable",
        transcript_webhook_timeout=0.5,
    )
    # Should not raise even when webhook is unreachable.
    await emit_turn(settings, {"role": "bot", "text": "hi"})


@pytest.mark.asyncio
async def test_emit_turn_fallback_on_webhook_failure(tmp_path):
    settings = Settings(
        transcript_webhook_url="http://127.0.0.1:9/unreachable",
        transcript_webhook_timeout=0.5,
        transcript_fallback_dir=str(tmp_path),
    )
    payload = {
        "interaction_id": "c1",
        "ani": "084",
        "dnis": "1555",
        "channel": "voice",
        "role": "caller",
        "transcript": "น้ำท่วม",
    }

    await emit_turn(settings, payload)

    files = list(tmp_path.glob("transcripts-*.jsonl"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert record["reason"] == "webhook_failed"
    assert record["error"]
    assert record["payload"]["interaction_id"] == "c1"
    assert record["payload"]["transcript"] == "น้ำท่วม"
    assert "saved_at" in record


@pytest.mark.asyncio
async def test_emit_turn_fallback_when_no_webhook_url(tmp_path):
    settings = Settings(
        transcript_webhook_url="",
        transcript_fallback_dir=str(tmp_path),
    )

    await emit_turn(settings, {"interaction_id": "c2", "role": "bot", "transcript": "รับทราบ"})

    files = list(tmp_path.glob("transcripts-*.jsonl"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert record["reason"] == "no_webhook_url"
    assert record["payload"]["transcript"] == "รับทราบ"

def test_build_turn_payload_prefers_architect_input_variables():
    params = {
        "conversationId": "conv-1",
        "participant": {"ani": "+66800000000", "dnis": "+6620000000"},
        "inputVariables": {
            "interaction_id": "CALL-9042-DEMO",
            "ani": "0847685368",
            "dnis": "02-096-6763",
        },
    }

    payload = build_turn_payload(params, "session-1", "caller", "มีน้ำท่วม")

    assert payload == {
        "interaction_id": "CALL-9042-DEMO",
        "ani": "0847685368",
        "dnis": "02-096-6763",
        "channel": "voice",
        "role": "caller",
        "transcript": "มีน้ำท่วม",
    }


def test_build_turn_payload_falls_back_to_participant():
    params = {
        "conversationId": "conv-1",
        "participant": {"ani": "+66800000000", "dnis": "+6620000000"},
    }

    payload = build_turn_payload(params, "session-1", "bot", "สวัสดี")

    assert payload["interaction_id"] == "conv-1"
    assert payload["ani"] == "+66800000000"
    assert payload["dnis"] == "+6620000000"


def test_build_turn_payload_falls_back_to_session_id():
    payload = build_turn_payload({}, "session-9", "bot", "สวัสดี")

    assert payload["interaction_id"] == "session-9"
    assert payload["ani"] is None
    assert payload["dnis"] is None
    assert payload["channel"] == "voice"


def test_build_turn_payload_ignores_empty_input_variables():
    params = {
        "conversationId": "conv-1",
        "participant": {"ani": "111", "dnis": "222"},
        "inputVariables": {"interaction_id": "", "ani": None, "dnis": ""},
    }

    payload = build_turn_payload(params, "session-1", "caller", "hi")

    assert payload["interaction_id"] == "conv-1"
    assert payload["ani"] == "111"
    assert payload["dnis"] == "222"
