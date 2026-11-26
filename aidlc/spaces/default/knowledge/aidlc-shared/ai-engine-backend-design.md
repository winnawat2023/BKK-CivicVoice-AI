# AI Engine backend — feature design note

Author: Peerapun Sinyu (AI Engine & Data Engineer) · Date: 2026-11-24
Process: "AI-DLC-style, no engine" — this note is a feature record only. It does **not** modify
`aidlc-state.md` or any stage memory of intent `261120-civic-contact-center` (paused at contract-design).

Traceability to `.kiro/specs/bkk-civic-connect/{requirements,design,tasks}.md` and the FR/NFR ids:
see `ai-engine-traceability.md` (same folder).

## 1. Scope (team lead's list)

1. Core FastAPI backend — `src/backend/civic/` (app factory), entry `src/backend/main.py`.
2. Thai LLM prompt extracting intent, problem category, district (50), urgency — `civic/prompts.py`, `civic/classifier.py`.
3. Civic RAG over BKK regulations so the bot answers end-to-end — `civic/rag/`.
4. WebSocket gateway for live transcript & summary to the Agent Widget — `civic/hub.py`, `civic/pipeline.py`, `docs/websocket-protocol.md`.

## 2. Key decisions

| # | Decision | Why |
|---|---|---|
| D1 | Hybrid understanding: LLM → strict validation → cross-check with a deterministic rules engine; rules are the fallback (`engine` field says which). | LLM may be down/slow/malformed; the call must never stall. |
| D2 | LLM reply is a tiny one-line JSON with English codes (`intent, category, sub, district, urgency`); Thai summary, SLA, unit, action are filled in by code. | Measured vLLM decode ≈ 13 tok/s (docs claim 60–90). ~40 tokens ≈ 2.5–3 s instead of ~11 s. |
| D3 | Inquiry topic decided by rules only; category/sub arbitration uses rules as tie-breaker. | On the 29-case gold set the model got topic 4/7 and mixed up category/sub (clean+dust, traffic+tree); see §4. |
| D4 | Two-phase widget summary: instant rules summary `provisional:true`, then LLM summary. | Widget requirement ≤ 2 s; LLM takes ~3 s. |
| D5 | RAG: dependency-free curated keyword + char-bigram retrieval; answer is extractive by default (`RAG_USE_LLM=false`). If LLM paraphrase is on, every number must appear in the sources, else extractive is used. Below `RAG_MIN_SCORE` → "no information" + `transfer_to_agent`. | Instant, deterministic, cannot invent fees/deadlines. |
| D6 | Categories per lead's list: ถนน, ทางเท้า, ผิดกฎจราจร, ไฟฟ้า, ความสะอาด, อื่นๆ (+ `sub_category` for flood/tree/noise/vendor/dust/animal/equipment/emergency under อื่นๆ); all 50 districts; RAG topics: ID card, house registration, elderly allowance. | "Lead's list wins". |
| D7 | Privacy: tickets store neither transcript nor ANI (FR2.5/3.2). Transcript/ANI live only in the in-memory call session and are purged on `/calls/{id}/end`. One ticket per `interaction_id` (idempotent webhook). | Requirements FR2.5, FR3.2. |
| D8 | Ticket ID `BKK-{year}-{seq:04d}`; statuses รับเรื่องแล้ว / กำลังดำเนินการ / แก้ไขเสร็จ. | Spoken-friendly, sortable. |
| D9 | Conversation rules in the webhook: ask for location once (FR2.2); unclear → re-ask twice then transfer (FR7.1). | Requirements. |

## 3. Differences vs `requirements.md` / old prototype (to review with the lead)

* Category list differs from requirements.md (5 + อื่นๆ with sub-types instead of the earlier list); flood is `อื่นๆ / ท่อระบายน้ำ/น้ำท่วม`.
* Ticket ID format and "no transcript in ticket" differ from the previous prototype backend (replaced).
* FR7.2 says malformed LLM output = "not understood". Here malformed output falls back to the rules engine, which only says "not understood" when it also fails. Judged better for callers; needs sign-off.
* `docs/server-setup-plan.md` says vLLM is on DGX 100; it is actually reachable at **DGX 101 :8001** (model id `typhoon-8b`).

## 4. Measured results (2026-11-24, 29-case gold set `tests/data/eval_cases.jsonl`)

| Mode | intent | category | sub | district | urgency | topic | latency p50 / max |
|---|---|---|---|---|---|---|---|
| rules only | 100% | 100% | 100% | 100% | 100% | 100% | <1 ms |
| LLM (typhoon-8b @ DGX101) + validation + rules arbitration | 100% | 100% | 100% | 100% | 100% | 100% | 2.5 s / 3.0 s |

**Caveat:** the rules were tuned on this same gold set and the category/sub arbitration was tuned after
seeing the model's mistakes on it, so these numbers are optimistic. Run
`python scripts/04_eval_classifier.py --mode rules --csv opendata/raw/traffy_fondue/traffy_2569.csv --limit 500`
and collect real call transcripts before quoting accuracy. 49/50 districts occur in the real open-data CSV
(`--check-districts`).

## 5. Open items / risks

* **ASR integration not done** — the Typhoon Whisper service API is not documented in the repo. The backend exposes `POST /api/v1/calls/{id}/segments`; a forwarder is needed.
* **No authentication** on webhook/WebSocket. Add shared secret / token before leaving the lab network.
* RAG dataset `civic/rag/data/bkk_regulations.json` is a **SAMPLE, unverified** — must be replaced/validated against official BKK sources before real citizens hear it.
* LLM throughput is ~13 tok/s; check whether vLLM is shared with another workload or mis-configured (not investigated: no server access was used).
* Credentials for both DGX hosts sit in project docs/chat history — rotate them and keep secrets out of the repo. `.env.example` contains none.
* Hub/session state is in-memory: single uvicorn worker only.

## 6. Verification

`cd src/backend && python -m pytest --cov=civic` — all tests pass, ~95% coverage (target 80%).
