"""SQLite ticket store.

Privacy (FR2.5 / FR3.2): a ticket never holds the spoken transcript or the caller's phone number.
Those only live in the short-lived in-memory call session (see ``hub.py``).
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .schemas import TICKET_STATUSES, Classification

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id       TEXT NOT NULL UNIQUE,
    year            INTEGER NOT NULL,
    seq             INTEGER NOT NULL,
    interaction_id  TEXT NOT NULL UNIQUE,
    category        TEXT,
    sub_category    TEXT,
    district        TEXT,
    location_detail TEXT NOT NULL DEFAULT '',
    urgency         TEXT NOT NULL,
    summary_lines   TEXT NOT NULL,
    suggested_action TEXT NOT NULL DEFAULT '',
    target_unit     TEXT NOT NULL DEFAULT '',
    sla_days        INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL,
    dispatched      INTEGER NOT NULL DEFAULT 0,
    dispatched_at   TEXT,
    engine          TEXT NOT NULL DEFAULT 'rules',
    confidence      REAL NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE (year, seq)
);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_district ON tickets(district);
"""


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["summary_lines"] = json.loads(data["summary_lines"])
    data["dispatched"] = bool(data["dispatched"])
    data.pop("id", None)
    data.pop("year", None)
    data.pop("seq", None)
    return data


class TicketStore:
    def __init__(self, path: str = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------------------------------------------------------------- create
    def create_ticket(self, interaction_id: str, c: Classification) -> tuple[dict[str, Any], bool]:
        """Create the ticket for a call. Idempotent: one call produces at most one ticket."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM tickets WHERE interaction_id = ?", (interaction_id,)
            ).fetchone()
            if existing is not None:
                return _row(existing), False  # type: ignore[return-value]
            year = dt.date.today().year
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                seq = (
                    self._conn.execute(
                        "SELECT COALESCE(MAX(seq), 0) FROM tickets WHERE year = ?", (year,)
                    ).fetchone()[0]
                    + 1
                )
                ticket_id = f"BKK-{year}-{seq:04d}"
                now = _now()
                self._conn.execute(
                    """INSERT INTO tickets (ticket_id, year, seq, interaction_id, category, sub_category,
                           district, location_detail, urgency, summary_lines, suggested_action, target_unit,
                           sla_days, status, engine, confidence, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ticket_id, year, seq, interaction_id, c.category, c.sub_category, c.district,
                        c.location_detail, c.urgency, json.dumps(c.summary_lines, ensure_ascii=False),
                        c.suggested_action, c.target_unit, c.estimated_sla_days, TICKET_STATUSES[0],
                        c.engine, c.confidence, now, now,
                    ),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
            return self.get(ticket_id), True  # type: ignore[return-value]

    # ------------------------------------------------------------------ read
    def get(self, ticket_id: str) -> dict[str, Any] | None:
        with self._lock:
            return _row(
                self._conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
            )

    def get_by_interaction(self, interaction_id: str) -> dict[str, Any] | None:
        with self._lock:
            return _row(
                self._conn.execute(
                    "SELECT * FROM tickets WHERE interaction_id = ?", (interaction_id,)
                ).fetchone()
            )

    def list_tickets(
        self, *, status: str | None = None, district: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM tickets WHERE 1=1", []
        if status:
            sql += " AND status = ?"
            args.append(status)
        if district:
            sql += " AND district = ?"
            args.append(district)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(max(1, min(limit, 500)))
        with self._lock:
            return [_row(r) for r in self._conn.execute(sql, args).fetchall()]  # type: ignore[misc]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]

    # ----------------------------------------------------------------- write
    def update_status(self, ticket_id: str, status: str) -> dict[str, Any] | None:
        if status not in TICKET_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        with self._lock:
            cur = self._conn.execute(
                "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
                (status, _now(), ticket_id),
            )
            if cur.rowcount == 0:
                return None
            return self.get(ticket_id)

    def mark_dispatched(self, ticket_id: str) -> dict[str, Any] | None:
        """1-click dispatch to the district office (idempotent)."""
        with self._lock:
            now = _now()
            cur = self._conn.execute(
                """UPDATE tickets SET dispatched = 1, dispatched_at = COALESCE(dispatched_at, ?),
                       status = CASE WHEN status = ? THEN ? ELSE status END, updated_at = ?
                   WHERE ticket_id = ?""",
                (now, TICKET_STATUSES[0], TICKET_STATUSES[1], now, ticket_id),
            )
            if cur.rowcount == 0:
                return None
            return self.get(ticket_id)
