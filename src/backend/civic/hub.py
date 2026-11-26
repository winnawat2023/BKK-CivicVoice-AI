"""WebSocket gateway: in-memory call sessions + fan-out of live events to Agent Widgets.

Event envelope (JSON text frame, server -> widget)::

    {"event": "<name>", "interaction_id": "...", "ts": "<ISO-8601>", "data": {...}}

Events: connected, snapshot, transcript, summary, ticket, live_update (legacy), dispatch_result,
ack, error, pong. See ``docs/websocket-protocol.md``.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("bkk-civic-voice.hub")

MONITOR_CHANNEL = "*"  # a subscriber on "*" receives the events of every call
SEND_TIMEOUT_S = 2.0


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="milliseconds")


def make_event(event: str, interaction_id: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"event": event, "interaction_id": interaction_id, "ts": now_iso(), "data": data}


@dataclass
class CallSession:
    """Ephemeral per-call state. Holds the transcript and ANI ONLY in memory (never in a ticket)."""

    interaction_id: str
    ani: str = ""
    max_segments: int = 200
    created_at: float = field(default_factory=time.monotonic)
    last_seen: float = field(default_factory=time.monotonic)
    segments: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] | None = None
    ticket: dict[str, Any] | None = None
    classification: Any = None  # latest Classification; lets the widget's "Create Ticket" reuse it
    _seq: int = 0

    def add_segment(self, text: str, speaker: str = "caller", is_final: bool = True) -> dict[str, Any]:
        self._seq += 1
        self.last_seen = time.monotonic()
        seg = {"seq": self._seq, "speaker": speaker, "text": text, "is_final": is_final, "ts": now_iso()}
        # A new partial replaces the previous partial of the same speaker (live ASR rewriting).
        if self.segments and not self.segments[-1]["is_final"] and self.segments[-1]["speaker"] == speaker:
            self.segments[-1] = seg
        else:
            self.segments.append(seg)
        if len(self.segments) > self.max_segments:
            del self.segments[: len(self.segments) - self.max_segments]
        return seg

    def caller_text(self) -> str:
        return " ".join(s["text"] for s in self.segments if s["speaker"] == "caller" and s["is_final"])

    def snapshot(self) -> dict[str, Any]:
        return {
            "caller_ani": self.ani,
            "transcript": list(self.segments),
            "summary": self.summary,
            "ticket": self.ticket,
        }


class SessionManager:
    def __init__(self, ttl_s: int = 3600, max_segments: int = 200):
        self._ttl = ttl_s
        self._max_segments = max_segments
        self._sessions: dict[str, CallSession] = {}

    def get_or_create(self, interaction_id: str, ani: str | None = None) -> CallSession:
        self.purge_expired()
        session = self._sessions.get(interaction_id)
        if session is None:
            session = CallSession(interaction_id, max_segments=self._max_segments)
            self._sessions[interaction_id] = session
        if ani:
            session.ani = ani
        session.last_seen = time.monotonic()
        return session

    def get(self, interaction_id: str) -> CallSession | None:
        return self._sessions.get(interaction_id)

    def drop(self, interaction_id: str) -> None:
        self._sessions.pop(interaction_id, None)

    def purge_expired(self) -> int:
        cutoff = time.monotonic() - self._ttl
        stale = [k for k, s in self._sessions.items() if s.last_seen < cutoff]
        for key in stale:
            del self._sessions[key]
        return len(stale)

    def __len__(self) -> int:
        return len(self._sessions)


class ConnectionHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, interaction_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(interaction_id, set()).add(ws)

    def disconnect(self, interaction_id: str, ws: WebSocket) -> None:
        peers = self._connections.get(interaction_id)
        if peers:
            peers.discard(ws)
            if not peers:
                del self._connections[interaction_id]

    def count(self, interaction_id: str | None = None) -> int:
        if interaction_id is None:
            return sum(len(p) for p in self._connections.values())
        return len(self._connections.get(interaction_id, ()))

    async def send(self, ws: WebSocket, event: dict[str, Any]) -> bool:
        try:
            await asyncio.wait_for(ws.send_text(json.dumps(event, ensure_ascii=False)), SEND_TIMEOUT_S)
            return True
        except Exception as exc:  # closed socket, slow client, ...
            logger.info("Dropping widget connection: %s", type(exc).__name__)
            return False

    async def broadcast(self, interaction_id: str, event: dict[str, Any]) -> int:
        """Send to every widget watching this call (and monitors). Returns how many received it."""
        targets = [
            (channel, ws)
            for channel in (interaction_id, MONITOR_CHANNEL)
            for ws in list(self._connections.get(channel, ()))
        ]
        if not targets:
            return 0
        results = await asyncio.gather(*(self.send(ws, event) for _, ws in targets))
        for (channel, ws), ok in zip(targets, results):
            if not ok:
                self.disconnect(channel, ws)
        return sum(1 for ok in results if ok)
