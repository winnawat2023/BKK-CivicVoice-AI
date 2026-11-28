"""ASGI entrypoint: WSS endpoint for the Genesys Audio Connector.

Run locally::

    uvicorn app.main:app --host 0.0.0.0 --port 8080

For TLS (required by Genesys Cloud in production) either terminate TLS at a
load balancer / reverse proxy or pass ``--ssl-keyfile`` / ``--ssl-certfile``
to uvicorn.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from fastapi import FastAPI, WebSocket

from .audiohook.messages import PROTOCOL_VERSION  # noqa: F401  (re-exported)
from .audiohook.session import AudioHookSession
from .audiohook.signature import (
    REQUIRED_COMPONENTS,
    HttpRequestInfo,
    canonicalize_header,
    verify_request,
)
from .config import Settings, get_settings

logger = logging.getLogger("app")


# ---------------------------------------------------------------------------
# Handshake request reconstruction
# ---------------------------------------------------------------------------
def _request_info(websocket: WebSocket) -> HttpRequestInfo:
    scope = websocket.scope

    # ``scope["path"]`` is URL-decoded; the signature is computed over the raw
    # request target, so prefer ``raw_path`` when the server provides it.
    raw_path: Optional[bytes] = scope.get("raw_path")
    if raw_path:
        path = raw_path.decode("latin-1")
    else:
        path = scope.get("path", "/")

    query_string: bytes = scope.get("query_string", b"") or b""
    target = path + ("?" + query_string.decode("latin-1") if query_string else "")

    headers = {
        key.lower(): canonicalize_header(value)
        for key, value in websocket.headers.items()
    }
    authority = headers.get("host") or websocket.url.netloc
    scheme = scope.get("scheme", "https")

    return HttpRequestInfo(
        method="GET",
        target=target,
        authority=authority,
        headers=headers,
        scheme=scheme,
    )


def authorize(websocket: WebSocket, settings: Settings) -> Tuple[bool, str]:
    """Authenticate the upgrade request (signature + API key)."""

    if not settings.verify_signature:
        return True, "signature verification disabled"

    api_key = websocket.headers.get("x-api-key")
    if not api_key:
        if settings.allow_unsigned:
            return True, "unsigned connections allowed"
        return False, "missing X-API-KEY header"

    if settings.genesys_api_key and api_key != settings.genesys_api_key:
        return False, "unknown API key"

    secret = settings.genesys_client_secret
    if not secret:
        if settings.allow_unsigned:
            return True, "no client secret configured; unsigned allowed"
        return False, "no client secret configured"

    result = verify_request(
        secret,
        _request_info(websocket),
        api_key=api_key,
        required_components=REQUIRED_COMPONENTS,
        max_age=settings.max_signature_age,
    )
    if result.ok:
        return True, "verified"
    if result.code == "UNSIGNED" and settings.allow_unsigned:
        return True, "unsigned connections allowed"

    return False, f"{result.code}: {result.reason}"


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------
async def audiohook_endpoint(websocket: WebSocket, path: str = "") -> None:
    settings = get_settings()

    ok, reason = authorize(websocket, settings)
    if not ok:
        client = websocket.client
        logger.warning("rejected AudioHook connection from %s: %s", client, reason)
        # Closing before accept makes the ASGI server answer the handshake with
        # an HTTP error instead of opening a WebSocket.
        await websocket.close(code=1008)
        return

    await websocket.accept()
    session = AudioHookSession(
        websocket,
        settings,
        session_id=websocket.headers.get("audiohook-session-id"),
    )
    logger.info(
        "AudioHook connection accepted from %s (session=%s)",
        websocket.client,
        session.session_id,
    )
    await session.run()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    app = FastAPI(
        title="Genesys Audio Connector <-> AI voice bridge",
        version="0.2.0",
    )

    @app.get("/healthz")
    async def healthz() -> dict:
        return {
            "status": "ok",
            "ai_provider": settings.provider,
            "ai_configured": settings.ai_ready,
            "openai_configured": settings.openai_ready,
            "gemini_configured": settings.gemini_ready,
            "typhoon_configured": settings.typhoon_ready,
            "signature_verification": settings.verify_signature,
        }

    app.add_api_websocket_route(settings.audiohook_path, audiohook_endpoint)
    # Some clients/probes append an extra path segment (for example a session
    # id). Accept those so Genesys validation/connect attempts don't 403 on route
    # mismatch; the AudioHook session itself is identified by the message body.
    app.add_api_websocket_route(settings.audiohook_path + "/{path:path}", audiohook_endpoint)
    scheme = "wss" if settings.ssl_enabled else "ws"
    logger.info(
        "Audio Connector endpoint: %s://%s:%s%s",
        scheme,
        settings.host,
        settings.port,
        settings.audiohook_path,
    )
    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    settings = get_settings()
    uvicorn_kwargs = {}
    if settings.ssl_enabled:
        uvicorn_kwargs["ssl_certfile"] = settings.ssl_certfile
        uvicorn_kwargs["ssl_keyfile"] = settings.ssl_keyfile
        if settings.ssl_ca_certs.strip():
            uvicorn_kwargs["ssl_ca_certs"] = settings.ssl_ca_certs
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        **uvicorn_kwargs,
    )
