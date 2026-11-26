"""
BKK CivicVoice AI - Core FastAPI Backend entry point.

Run from the repo root (what the systemd unit does):   uvicorn src.backend.main:app --port 8000
or directly:                                           python src/backend/main.py

The implementation lives in the ``civic`` package next to this file:
  civic/app.py         REST + WebSocket gateway
  civic/classifier.py  Thai LLM (Typhoon) intent / category / district / urgency extraction
  civic/rag/           Civic RAG over BKK regulations
  civic/store.py       SQLite ticket store
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from civic.app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
