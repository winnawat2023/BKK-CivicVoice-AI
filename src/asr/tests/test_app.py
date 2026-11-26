"""REST + WebSocket behaviour with a fake engine and a fake CivicVoice API."""

from __future__ import annotations

import json
import time

import httpx
import numpy as np

from asr_service.engine import ASRError, AudioDecodeError, ModelLoadError, Transcript

from .conftest import THAI_TEXT, FakeBackend, FakeEngine, silence, make_settings, to_pcm16, tone

WAV_BYTES = b"RIFF$\x00\x00\x00WAVEfmt "  # content is irrelevant: the engine is a fake


def upload(client, data=WAV_BYTES, **form):
    return client.post("/v1/transcribe", files={"file": ("call.wav", data, "audio/wav")}, data=form)


# ------------------------------------------------------------------ health
def test_root_and_health(client, engine):
    assert client.get("/").json()["status"] == "online"
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["model"] == "large-v3-turbo"
    assert body["allowed_languages"] == ["th", "en"] and body["backend_url"] == "http://backend.test"
    assert "backend" not in body


def test_health_can_probe_the_backend(client, backend):
    body = client.get("/health", params={"check_backend": True}).json()
    assert body["backend"]["reachable"] is True
    assert backend.requests[0].url.path == "/api/v1/health"


def test_health_reports_unreachable_backend(make_client):
    c = make_client(back=FakeBackend(error=httpx.ConnectError("refused")))
    assert c.get("/health", params={"check_backend": True}).json()["backend"]["reachable"] is False


# ------------------------------------------------------------ /v1/transcribe
def test_transcribe_returns_text_without_forwarding_by_default(client, engine, backend):
    r = upload(client)
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == THAI_TEXT and body["language"] == "th"
    assert body["forwarded"] == {"attempted": False, "ok": False, "status": None, "error": None}
    assert backend.requests == []
    assert engine.calls[0][0] == WAV_BYTES and engine.calls[0][1] is None


def test_transcribe_forwards_to_the_segments_endpoint(client, backend):
    r = upload(client, interaction_id="CALL-9042-DEMO", ani="0812345678")
    assert r.status_code == 200 and r.json()["forwarded"]["ok"] is True
    (req,) = backend.requests
    assert req.method == "POST" and req.url.path == "/api/v1/calls/CALL-9042-DEMO/segments"
    assert json.loads(req.content) == {"text": THAI_TEXT, "speaker": "caller", "is_final": True, "ani": "0812345678"}


def test_transcribe_can_send_other_speaker_and_partial(client, backend):
    upload(client, interaction_id="C1", speaker="agent", is_final="false")
    assert backend.bodies() == [{"text": THAI_TEXT, "speaker": "agent", "is_final": False}]


def test_forward_false_and_missing_interaction_id_skip_the_backend(client, backend):
    upload(client, interaction_id="C1", forward="false")
    upload(client)
    assert backend.requests == []


def test_forward_default_can_be_turned_off(make_client, backend):
    c = make_client(make_settings(forward_default=False))
    upload(c, interaction_id="C1")
    assert backend.requests == []
    upload(c, interaction_id="C1", forward="true")
    assert len(backend.requests) == 1


def test_interaction_id_is_url_quoted(client, backend):
    upload(client, interaction_id="a b/c")
    assert backend.requests[0].url.raw_path.decode() == "/api/v1/calls/a%20b%2Fc/segments"


def test_language_form_field_reaches_the_engine(client, engine):
    upload(client, language="en")
    assert engine.calls[0][1] == "en"


def test_empty_transcript_is_not_forwarded(make_client, backend):
    c = make_client(eng=FakeEngine(Transcript(text="", language="th", duration=1.0)))
    body = upload(c, interaction_id="C1").json()
    assert body["text"] == "" and body["forwarded"]["attempted"] is False
    assert backend.requests == []


def test_backend_down_does_not_fail_the_transcription(make_client):
    c = make_client(back=FakeBackend(error=httpx.ConnectError("refused")))
    r = upload(c, interaction_id="C1")
    assert r.status_code == 200 and r.json()["text"] == THAI_TEXT
    assert r.json()["forwarded"]["ok"] is False and "ConnectError" in r.json()["forwarded"]["error"]


def test_backend_rejection_is_reported(make_client):
    c = make_client(back=FakeBackend(status=422))
    fwd = upload(c, interaction_id="C1").json()["forwarded"]
    assert fwd["ok"] is False and fwd["status"] == 422


def test_upload_validation(make_client):
    assert upload(make_client(), data=b"").status_code == 400
    assert upload(make_client(make_settings(max_upload_mb=0)), data=b"x").status_code == 413
    assert make_client().post("/v1/transcribe").status_code == 422  # no file at all
    assert upload(make_client(), speaker="robot").status_code == 422


def test_engine_failures_map_to_http_status(make_client):
    cases = [(ModelLoadError("no model"), 503), (AudioDecodeError("bad audio"), 422), (ASRError("boom"), 500)]
    for error, status in cases:
        r = upload(make_client(eng=FakeEngine(error)))
        assert r.status_code == status and r.json()["detail"] == str(error)


# ---------------------------------------------------------- /v1/stream
def collect(ws, until="closed"):
    events = []
    while True:
        event = ws.receive_json()
        events.append(event)
        if event["event"] == until:
            return events


def test_stream_emits_final_for_an_utterance_and_forwards_it(client, engine, backend):
    with client.websocket_connect("/v1/stream/CALL-S1?ani=0812345678") as ws:
        ready = ws.receive_json()
        assert ready["event"] == "ready" and ready["interaction_id"] == "CALL-S1"
        assert ready["encoding"] == "pcm16" and ready["sample_rate"] == 16000 and ready["forwarding"] is True
        ws.send_bytes(to_pcm16(np.concatenate([tone(1.0), silence(1.0)])))
        final = ws.receive_json()
        assert final["event"] == "final" and final["text"] == THAI_TEXT and final["forwarded"] is True
        ws.send_text(json.dumps({"action": "end"}))
        assert collect(ws)[-1] == {"interaction_id": "CALL-S1", "event": "closed", "end_call": False}
    assert backend.bodies() == [{"text": THAI_TEXT, "speaker": "caller", "is_final": True, "ani": "0812345678"}]
    assert backend.requests[0].url.path == "/api/v1/calls/CALL-S1/segments"
    audio, language = engine.calls[0]
    assert audio.dtype == np.float32 and audio.size > 16000 and language is None


def test_stream_partial_then_final(make_client, backend):
    c = make_client(make_settings(partial_interval_ms=500))
    with c.websocket_connect("/v1/stream/CALL-P") as ws:
        ws.receive_json()
        ws.send_bytes(to_pcm16(np.concatenate([tone(2.0), silence(1.0)])))  # one burst -> 1 partial + final
        assert [ws.receive_json()["event"] for _ in range(2)] == ["partial", "final"]
        ws.send_text('{"action":"end"}')
        collect(ws)
    assert [b["is_final"] for b in backend.bodies()] == [False, True]


def test_stream_flushes_an_open_utterance_when_the_client_ends(client, backend):
    with client.websocket_connect("/v1/stream/CALL-F") as ws:
        ws.receive_json()
        ws.send_bytes(to_pcm16(tone(1.0)))  # caller still talking when the stream stops
        ws.send_text('{"action":"end"}')
        events = collect(ws)
    assert [e["event"] for e in events] == ["final", "closed"]
    assert len(backend.requests) == 1


def test_stream_flushes_when_the_socket_just_drops(client, backend):
    with client.websocket_connect("/v1/stream/CALL-D") as ws:
        ws.receive_json()
        ws.send_bytes(to_pcm16(tone(1.0)))
        ws.close()  # caller hangs up without sending {"action":"end"}
        deadline = time.time() + 3  # the TestClient cancels the app on exit, so wait for the handler to finish
        while not backend.requests and time.time() < deadline:
            time.sleep(0.02)
    assert len(backend.requests) == 1  # the open utterance was still transcribed and forwarded


def test_stream_accepts_8khz_mulaw_telephony_audio(client, engine):
    # mu-law 0x00 is full-scale negative (loud), 0xFF is zero: 1 s of "speech" then 1 s of silence at 8 kHz
    with client.websocket_connect("/v1/stream/CALL-G711?encoding=mulaw&sample_rate=8000&language=th") as ws:
        ready = ws.receive_json()
        assert ready["encoding"] == "mulaw" and ready["sample_rate"] == 8000 and ready["language"] == "th"
        ws.send_bytes(bytes([0x00]) * 8000 + bytes([0xFF]) * 8000)
        assert ws.receive_json()["event"] == "final"
        ws.send_text('{"action":"end"}')
        collect(ws)
    audio, language = engine.calls[0]
    assert language == "th" and audio.size > 16000  # resampled up to 16 kHz


def test_stream_end_call_flag_closes_the_call_on_the_backend(client, backend):
    with client.websocket_connect("/v1/stream/CALL-E") as ws:
        ws.receive_json()
        ws.send_text('{"action":"end","end_call":true}')
        events = collect(ws)
    assert events[-1]["end_call"] is True
    assert [r.url.path for r in backend.requests] == ["/api/v1/calls/CALL-E/end"]


def test_stream_without_forwarding_only_returns_events(client, backend):
    with client.websocket_connect("/v1/stream/CALL-N?forward=false") as ws:
        assert ws.receive_json()["forwarding"] is False
        ws.send_bytes(to_pcm16(np.concatenate([tone(1.0), silence(1.0)])))
        final = ws.receive_json()
        assert final["event"] == "final" and "forwarded" not in final
        ws.send_text('{"action":"end"}')
        collect(ws)
    assert backend.requests == []


def test_stream_control_messages(client):
    with client.websocket_connect("/v1/stream/CALL-C") as ws:
        ws.receive_json()
        ws.send_text('{"action":"ping"}')
        assert ws.receive_json()["event"] == "pong"
        ws.send_text("not json")
        assert ws.receive_json()["event"] == "error"
        ws.send_text('{"action":"end"}')
        collect(ws)


def test_stream_rejects_bad_parameters(client):
    for query in ("encoding=opus", "sample_rate=100", "sample_rate=999999"):
        with client.websocket_connect(f"/v1/stream/CALL-X?{query}") as ws:
            assert ws.receive_json()["event"] == "error"


def test_stream_reports_engine_errors_and_keeps_going(make_client):
    c = make_client(eng=FakeEngine(ModelLoadError("no model")))
    with c.websocket_connect("/v1/stream/CALL-ERR") as ws:
        ws.receive_json()
        ws.send_bytes(to_pcm16(np.concatenate([tone(1.0), silence(1.0)])))
        err = ws.receive_json()
        assert err["event"] == "error" and "no model" in err["message"]
        ws.send_text('{"action":"end"}')
        collect(ws)


def test_stream_ignores_noise_only_audio(client, backend):
    with client.websocket_connect("/v1/stream/CALL-Q") as ws:
        ws.receive_json()
        ws.send_bytes(to_pcm16(silence(2.0)))
        ws.send_text('{"action":"end"}')
        events = collect(ws)
    assert [e["event"] for e in events] == ["closed"] and backend.requests == []
