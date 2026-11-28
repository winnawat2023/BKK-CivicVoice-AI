"""Local test client that speaks the Genesys AudioHook protocol.

It simulates what Genesys Cloud does: connect, ``open``, stream PCMU audio,
optionally ``ping``, then ``close`` and wait for ``closed``.  Use it to verify
your WSS endpoint without wiring a real Genesys integration.

Examples
--------
Unsigned (server started with ``AUDIOHOOK_ALLOW_UNSIGNED=true``)::

    python scripts/fake_genesys_client.py --url ws://localhost:8080/api/v1/audiohook/ws

Signed (matches GENESYS_API_KEY / GENESYS_CLIENT_SECRET)::

    python scripts/fake_genesys_client.py \
        --url ws://localhost:8080/api/v1/audiohook/ws \
        --api-key change-me --client-secret change-me-too
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import struct
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import websockets  # noqa: E402

from app.ai.audio import pcm16_to_ulaw  # noqa: E402
from app.audiohook.messages import client_message, to_duration  # noqa: E402
from app.audiohook.signature import (  # noqa: E402
    HttpRequestInfo,
    create_signature_headers,
)

NULL_UUID = "00000000-0000-0000-0000-000000000000"


def build_open_message(
    session_id: str, *, probe: bool, input_variables: dict | None = None
) -> dict:
    conversation_id = NULL_UUID if probe else str(uuid.uuid4())
    participant_id = NULL_UUID if probe else str(uuid.uuid4())
    parameters = {
        "organizationId": str(uuid.uuid4()),
        "conversationId": conversation_id,
        "participant": {
            "id": participant_id,
            "ani": "+1-555-555-1234",
            "aniName": "Test Caller",
            "dnis": "+1-800-555-6789",
        },
        "media": [
            {
                "type": "audio",
                "format": "PCMU",
                "channels": ["external"],
                "rate": 8000,
            }
        ],
        "language": "en-US",
    }
    if input_variables:
        parameters["inputVariables"] = input_variables
    return client_message(
        session_id,
        "open",
        1,
        0,
        "PT0S",
        parameters,
    )


def make_headers(args, session_id: str) -> tuple[dict[str, str], str]:
    parsed = urlparse(args.url)
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    authority = parsed.netloc

    headers = {
        "host": authority,
        "audiohook-organization-id": str(uuid.uuid4()),
        "audiohook-correlation-id": str(uuid.uuid4()),
        "audiohook-session-id": session_id,
        "audiohook-retry-attempt": "0",
        "user-agent": "GenesysCloud-AudioHook-Client (fake)",
    }

    if args.client_secret:
        headers["x-api-key"] = args.api_key
        request = HttpRequestInfo(
            method="GET",
            target=target,
            authority=authority,
            headers=headers,
            scheme="https" if parsed.scheme in ("wss", "https") else "http",
        )
        signed = create_signature_headers(
            args.client_secret, request, keyid=args.api_key
        )
        headers.update(signed)

    # ``websockets`` sets Host itself from the URL; drop it to avoid duplicates.
    wire_headers = {k: v for k, v in headers.items() if k.lower() != "host"}
    return wire_headers, target


def tone_ulaw(duration_ms: int, frequency: float = 1000.0, rate: int = 8000) -> bytes:
    count = int(rate * duration_ms / 1000)
    samples = []
    for i in range(count):
        value = 0.3 * math.sin(2 * math.pi * frequency * i / rate)
        samples.append(int(value * 32767))
    pcm = struct.pack(f"<{count}h", *samples)
    return pcm16_to_ulaw(pcm)


async def send_tone(ws, seconds: float) -> None:
    frame = tone_ulaw(20)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        await ws.send(frame)
        await asyncio.sleep(0.02)


async def run(args) -> int:
    session_id = str(uuid.uuid4())
    headers, target = make_headers(args, session_id)

    print(f"connecting to {args.url} (target={target})")
    parsed = urlparse(args.url)
    ssl_context = None
    if parsed.scheme == "wss":
        import ssl

        ssl_context = ssl.create_default_context()
        if args.insecure:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        elif args.cafile:
            ssl_context.load_verify_locations(args.cafile)

    async with websockets.connect(
        args.url, extra_headers=headers, max_size=None, ssl=ssl_context
    ) as ws:
        await ws.send(
            json.dumps(
                build_open_message(
                    session_id,
                    probe=args.probe,
                    input_variables=parse_input_variables(args.input_var),
                )
            )
        )

        state = {
            "server_seq": 0,
            "client_seq": 1,
            "audio_bytes": 0,
            "events": 0,
        }
        opened = asyncio.Event()
        closed = asyncio.Event()

        async def receiver() -> None:
            while True:
                raw = await ws.recv()
                if isinstance(raw, (bytes, bytearray)):
                    state["audio_bytes"] += len(raw)
                    continue
                message = json.loads(raw)
                state["server_seq"] = max(
                    state["server_seq"], int(message.get("seq", 0))
                )
                print(f"<- {message.get('type')} seq={message.get('seq')}")
                if message.get("type") == "opened":
                    opened.set()
                elif message.get("type") == "event":
                    state["events"] += 1
                elif message.get("type") == "disconnect":
                    print(f"   disconnect: {message.get('parameters')}")
                elif message.get("type") == "closed":
                    closed.set()
                    return

        receiver_task = asyncio.create_task(receiver())

        try:
            await asyncio.wait_for(opened.wait(), timeout=5.0)
            print("session opened")

            if args.probe:
                await asyncio.sleep(0.2)
            else:
                if args.ping:
                    state["client_seq"] += 1
                    await ws.send(
                        json.dumps(
                            client_message(
                                session_id,
                                "ping",
                                state["client_seq"],
                                state["server_seq"],
                                to_duration(0.0),
                                {},
                            )
                        )
                    )
                    await asyncio.sleep(0.2)

                await send_tone(ws, args.seconds)

            state["client_seq"] += 1
            await ws.send(
                json.dumps(
                    client_message(
                        session_id,
                        "close",
                        state["client_seq"],
                        state["server_seq"],
                        to_duration(args.seconds),
                        {"reason": "end"},
                    )
                )
            )

            try:
                await asyncio.wait_for(closed.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                print("no 'closed' message received within 10s")
                return 2
        finally:
            receiver_task.cancel()
            try:
                await receiver_task
            except (asyncio.CancelledError, Exception):
                pass

    print(
        "done: received %d audio bytes, %d events, server_seq=%d"
        % (state["audio_bytes"], state["events"], state["server_seq"])
    )
    return 0


def parse_input_variables(items: list[str] | None) -> dict:
    result: dict[str, str] = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise SystemExit(f"--input-var expects KEY=VALUE, got {item!r}")
        result[key] = value
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="ws://localhost:8080/api/v1/audiohook/ws",
        help="AudioHook WSS URL of your server",
    )
    parser.add_argument("--api-key", default="change-me")
    parser.add_argument(
        "--client-secret",
        default="",
        help="Sign the upgrade request when set (must match the server secret)",
    )
    parser.add_argument(
        "--seconds", type=float, default=3.0, help="how long to stream the test tone"
    )
    parser.add_argument("--ping", action="store_true", help="send one ping/pong")
    parser.add_argument(
        "--probe", action="store_true", help="send a connection probe (null UUIDs)"
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="skip TLS verification for wss:// (dev/self-signed only)",
    )
    parser.add_argument(
        "--cafile",
        default="",
        help="CA bundle to trust for wss:// (useful for local self-signed certs)",
    )
    parser.add_argument(
        "--input-var",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Architect input variable to include in the open message "
        "(repeatable, e.g. --input-var interaction_id=CALL-1)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
