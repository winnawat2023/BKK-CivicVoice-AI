# WebSocket protocol — Agent Widget gateway

Endpoints (FastAPI, same port as the REST API):

| URL | Purpose |
|---|---|
| `ws://<host>:8000/ws/agent/{interaction_id}` | One call. Widget connects as soon as the Genesys screen-pop gives it the `interaction_id`. |
| `ws://<host>:8000/ws/monitor` | Every call (supervisor board / demo). Does not send a snapshot. |

Every server → client frame is one JSON envelope:

```json
{ "event": "summary", "interaction_id": "CALL-1", "ts": "2026-11-24T10:15:03.120", "data": { } }
```

## Server → widget events

| event | when | `data` |
|---|---|---|
| `connected` | right after connect | `{protocol: 1, server_time}` |
| `snapshot` | right after connect (agent channel) | `{caller_ani, transcript: [segment], summary, ticket}` — lets a widget opened mid-call catch up |
| `transcript` | each ASR segment (`POST /api/v1/calls/{id}/segments`) or webhook turn | `{speaker: caller\|bot\|agent, text, is_final, ts, caller_ani}` — sent immediately, never waits for the LLM |
| `summary` | AI analysis updated | see below |
| `ticket` | ticket created or status changed | `{ticket_id, status, category, sub_category, district, urgency, target_unit, sla_days, ...}` (no transcript, no phone number) |
| `live_update` | with every `summary` | legacy shape used by the first widget (`transcript`, `summary`, `category`, `district`, `urgency`, `ticket_id` …) |
| `ticket_result` | after `create_ticket` | `{success, ticket?, created?, error?}` |
| `dispatch_result` | after `dispatch` | `{success, ticket?, message \| error}` |
| `call_ended` | `POST /api/v1/calls/{id}/end` | `{ticket}` — after this, transcript and caller number are purged |
| `pong`, `error` | replies to the sending widget only | `{}` / `{message}` |

### `summary` data

```json
{
  "provisional": false,
  "intent": "complaint | inquiry | unclear",
  "category": "อื่นๆ", "sub_category": "ท่อระบายน้ำ/น้ำท่วม",
  "district": "คลองเตย", "location_detail": "ซอยสุขุมวิท 50",
  "urgency": "high", "urgency_th": "เร่งด่วน",
  "summary_lines": ["...", "...", "..."],
  "target_unit": "...", "suggested_action": "...", "sla_days": 1,
  "inquiry_topic": null, "answer": null, "ticket_id": "BKK-2026-0001",
  "engine": "llm | rules", "confidence": 0.8,
  "understood": true, "needs_location": false
}
```

**Two-phase summaries.** The vLLM on the DGX decodes slowly, so while it works the widget first receives a
summary with `"provisional": true` and `"engine": "rules"` (instant, keyword rules). When the LLM answers, a
second `summary` with `"provisional": false` replaces it. If the LLM is down or slow, the rules result is
the only (final) one. The widget should simply render whichever `summary` arrived last.

## Widget → server actions (JSON text frames)

| frame | effect |
|---|---|
| `{"action":"ping"}` | `pong` |
| `{"action":"snapshot"}` | `snapshot` (reply to sender only) |
| `{"action":"create_ticket"}` | **Create Ticket button.** Files the complaint the AI understood on this call (idempotent: one ticket per call). Broadcasts `ticket` (when new) and `ticket_result` `{success, ticket?, created?, error?}`; `success:false` when nothing categorised was understood yet |
| `{"action":"dispatch","ticket_id":"BKK-2026-0001"}` | marks the ticket dispatched; `dispatch_result` broadcast to all widgets of the call (`ticket_id` optional → ticket of this call) |
| `{"action":"set_status","ticket_id":"...","status":"กำลังดำเนินการ"}` | updates status; `ticket` event broadcast. Statuses: `รับเรื่องแล้ว`, `กำลังดำเนินการ`, `แก้ไขเสร็จ` |

Anything else → `error`.

## Who feeds the gateway

* **Genesys / voicebot** → `POST /api/v1/genesys/webhook` `{interaction_id, ani?, channel?, transcript | text_or_audio_stream, timestamp?}`. Returns
  `{next_action, reply_text, ticket_id, analysis, answer}`; `next_action` is one of `reply | answer |
  ask_location | ask_repeat | ticket_created | transfer_to_agent`.
* **ASR** (Faster-Whisper service, `src/asr`, port 5001) → `POST /api/v1/calls/{id}/segments`
  `{text, speaker?, is_final?, ani?}` for streaming partial/final transcript. The service does this itself when
  audio arrives with an `interaction_id` (file upload `POST /v1/transcribe` or live `WS /v1/stream/{id}`), so the
  widget just keeps receiving `transcript` events. See [asr-service.md](asr-service.md). *Still missing: the bridge
  from Genesys AudioHook / Media Streaming to the ASR stream endpoint.*
* **Call end** → `POST /api/v1/calls/{id}/end`.

## Not yet in place

* No authentication on webhook or sockets (anyone on the network can call them). Add a shared-secret header
  (webhook) and a token query parameter (WebSocket) before leaving the internal network.
* The hub is in-memory, single process: run uvicorn with one worker, or put Redis pub/sub behind `ConnectionHub`.
