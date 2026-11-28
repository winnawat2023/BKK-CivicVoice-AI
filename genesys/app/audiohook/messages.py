"""Message helpers for the Genesys AudioHook protocol (version 2).

The protocol mixes JSON text frames (metadata / control messages) with binary
frames (raw audio).  Genesys Cloud is always the *client*; this service is the
*server*.
"""

from __future__ import annotations

from typing import Any, Optional

PROTOCOL_VERSION = "2"
NULL_UUID = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------
def to_duration(seconds: float) -> str:
    """Format seconds as an ISO 8601 duration, e.g. ``PT1.5S``.

    The protocol uses fractional seconds with up to microsecond precision and
    expects ``PT0S`` for the zero position.
    """

    if seconds is None:
        seconds = 0.0
    # Avoid "-0" and keep a compact representation.
    text = f"{max(float(seconds), 0.0):.6f}".rstrip("0").rstrip(".")
    if text in ("", "0"):
        text = "0"
    return f"PT{text}S"


def server_message(
    msg_id: str,
    msg_type: str,
    seq: int,
    client_seq: int,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Build a server -> client message (uses ``clientseq``)."""

    return {
        "version": PROTOCOL_VERSION,
        "id": msg_id,
        "type": msg_type,
        "seq": seq,
        "clientseq": client_seq,
        "parameters": parameters,
    }


def client_message(
    msg_id: str,
    msg_type: str,
    seq: int,
    server_seq: int,
    position: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Build a client -> server message (uses ``serverseq`` and ``position``).

    Used by the local test client and the unit tests.
    """

    return {
        "version": PROTOCOL_VERSION,
        "id": msg_id,
        "type": msg_type,
        "seq": seq,
        "serverseq": server_seq,
        "position": position,
        "parameters": parameters,
    }


# ---------------------------------------------------------------------------
# Media negotiation
# ---------------------------------------------------------------------------
def choose_media(offered: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Pick one offered media entry.

    The server must return exactly one of the offered entries **unmodified**.
    We only support PCMU / 8000 Hz.  For the Audio Connector feature the only
    offered channel is ``external``; if a stereo (``external`` + ``internal``)
    offer arrives we still accept it so the same server can serve the monitor
    use case.
    """

    candidates = [
        media
        for media in offered
        if media.get("type") == "audio"
        and str(media.get("format", "")).upper() == "PCMU"
        and int(media.get("rate", 0)) == 8000
    ]
    if not candidates:
        return None

    # Prefer the caller-only stream (Audio Connector) when it is offered.
    for media in candidates:
        if list(media.get("channels", [])) == ["external"]:
            return media
    return candidates[0]


def is_connection_probe(open_parameters: dict[str, Any]) -> bool:
    """Detect a Genesys connection probe.

    A probe uses the null UUID for the conversation (and often for the
    participant).  It exists only to validate the endpoint / authentication,
    so there is no point opening an expensive AI session for it.
    """

    conversation_id = open_parameters.get("conversationId")
    if conversation_id == NULL_UUID:
        return True
    participant = open_parameters.get("participant") or {}
    participant_id = participant.get("id")
    return participant_id == NULL_UUID


# ---------------------------------------------------------------------------
# Event entities (server -> client)
# ---------------------------------------------------------------------------
def barge_in_entity() -> dict[str, Any]:
    """Tell Genesys to stop playing the audio we previously sent."""

    return {"type": "barge_in", "data": {}}


def bot_turn_response_entity(
    disposition: str = "match",
    text: Optional[str] = None,
    confidence: Optional[float] = None,
) -> dict[str, Any]:
    """Report the bot's turn result back to Genesys (historical reporting)."""

    data: dict[str, Any] = {"disposition": disposition}
    if text is not None:
        data["text"] = text
    if confidence is not None:
        data["confidence"] = confidence
    return {"type": "bot_turn_response", "data": data}
