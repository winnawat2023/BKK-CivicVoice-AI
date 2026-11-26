"""Transcript delivery helpers.

The bridge emits finalized caller/bot turns through callbacks. This module can
forward those turns to an external webhook without blocking the audio path.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

from .config import Settings

logger = logging.getLogger("transcript")


def _pick(mapping: Any, *keys: str) -> Any:
    """Case-insensitive lookup that ignores missing/empty values."""

    if not isinstance(mapping, dict):
        return None
    lowered = {str(k).lower(): v for k, v in mapping.items()}
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return value
    return None


def build_turn_payload(
    open_parameters: dict[str, Any] | None,
    session_id: str | None,
    role: str,
    text: str,
) -> dict[str, Any]:
    """Build the webhook body from the Genesys AudioHook ``open`` parameters.

    Architect's *Call Audio Connector* action sends its input variables under
    ``parameters.inputVariables``.  Older/other deployments may only provide the
    built-in ``conversationId`` and ``participant`` fields, so those are used as
    fallbacks.
    """

    params = open_parameters or {}
    participant = params.get("participant") or {}
    input_vars = params.get("inputVariables") or {}

    interaction_id = (
        _pick(input_vars, "interaction_id", "interactionId")
        or params.get("conversationId")
        or session_id
    )
    return {
        "interaction_id": interaction_id,
        "ani": _pick(input_vars, "ani") or participant.get("ani"),
        "dnis": _pick(input_vars, "dnis") or participant.get("dnis"),
        "channel": "voice",
        "role": role,
        "transcript": text,
    }


def _post_json(url: str, payload: dict[str, Any], timeout: float, token: str) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "AIVoiceGenesys-Transcript/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = request.Request(url, data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout) as resp:
        # Drain body to allow connection reuse by urllib internals.
        resp.read()


def _write_fallback(
    fallback_dir: str, payload: dict[str, Any], reason: str, error: str = ""
) -> Path | None:
    directory = (fallback_dir or "").strip()
    if not directory:
        return None

    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / f"transcripts-{datetime.now(timezone.utc):%Y%m%d}.jsonl"
    record = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "error": error,
        "payload": payload,
    }
    with file_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return file_path


async def emit_turn(settings: Settings, payload: dict[str, Any]) -> None:
    """POST a transcript turn to webhook; fall back to local JSONL on failure."""

    url = (settings.transcript_webhook_url or "").strip()
    fallback_dir = (settings.transcript_fallback_dir or "").strip()
    body = dict(payload)
    body.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

    if not url:
        if fallback_dir:
            path = await asyncio.to_thread(
                _write_fallback, fallback_dir, body, "no_webhook_url"
            )
            logger.info("transcript saved to fallback: %s", path)
        return

    timeout = max(float(settings.transcript_webhook_timeout), 0.1)
    token = (settings.transcript_webhook_bearer_token or "").strip()

    try:
        await asyncio.to_thread(_post_json, url, body, timeout, token)
        return
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            detail = ""
        error = f"HTTP {exc.code} {exc.reason}{f' - {detail}' if detail else ''}"
        logger.warning("transcript webhook failed: %s", error)
    except (URLError, TimeoutError, Exception) as exc:
        error = str(exc)
        logger.warning("transcript webhook failed: %s", error)

    if fallback_dir:
        try:
            path = await asyncio.to_thread(
                _write_fallback, fallback_dir, body, "webhook_failed", error
            )
            logger.warning("transcript saved to fallback: %s", path)
        except Exception:
            logger.exception("transcript fallback write failed")
