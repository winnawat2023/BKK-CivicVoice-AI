"""
BKK CivicVoice AI - ASR service entry point (Faster-Whisper, default port 5001).

Run from ``src/asr``:   uvicorn main:app --host 0.0.0.0 --port 5001
or directly:            python main.py

The implementation lives in the ``asr_service`` package next to this file:
  asr_service/app.py        REST (/v1/transcribe) + WebSocket (/v1/stream/{interaction_id})
  asr_service/engine.py     Faster-Whisper model wrapper (lazy load, device auto-detect, TH/EN handling)
  asr_service/streaming.py  utterance detection for live audio (partial / final transcripts)
  asr_service/forwarder.py  hand-off to the CivicVoice API (POST /api/v1/calls/{id}/segments)
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from asr_service.app import create_app  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("ASR_PORT", "5001")))
