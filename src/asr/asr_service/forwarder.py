"""Hand-off to the CivicVoice API: transcript pieces go to ``POST /api/v1/calls/{id}/segments``."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings

logger = logging.getLogger("bkk-asr")


@dataclass
class ForwardResult:
    attempted: bool
    ok: bool = False
    status: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"attempted": self.attempted, "ok": self.ok, "status": self.status, "error": self.error}


class BackendForwarder:
    """Thin async client for the middleware. Failures are reported, never raised: a slow or down API must not
    stop the transcription itself."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = settings.backend_url
        self._client = httpx.AsyncClient(
            base_url=settings.backend_url,
            timeout=httpx.Timeout(settings.backend_timeout_s),
            transport=transport,
        )

    @staticmethod
    def _calls_path(interaction_id: str, tail: str) -> str:
        return f"/api/v1/calls/{quote(interaction_id, safe='')}/{tail}"

    async def _post(self, path: str, body: dict[str, Any] | None) -> ForwardResult:
        try:
            resp = await self._client.post(path, json=body)
        except httpx.HTTPError as exc:
            logger.warning("Backend unreachable (%s): %s", self.base_url, exc.__class__.__name__)
            return ForwardResult(True, False, None, f"{exc.__class__.__name__}: {exc}")
        if resp.status_code >= 400:
            logger.warning("Backend rejected %s: HTTP %s", path.rsplit("/", 1)[-1], resp.status_code)
            return ForwardResult(True, False, resp.status_code, resp.text[:200])
        return ForwardResult(True, True, resp.status_code)

    async def push_segment(
        self,
        interaction_id: str,
        text: str,
        *,
        speaker: str = "caller",
        is_final: bool = True,
        ani: str | None = None,
    ) -> ForwardResult:
        body: dict[str, Any] = {"text": text, "speaker": speaker, "is_final": is_final}
        if ani:
            body["ani"] = ani
        return await self._post(self._calls_path(interaction_id, "segments"), body)

    async def end_call(self, interaction_id: str) -> ForwardResult:
        return await self._post(self._calls_path(interaction_id, "end"), None)

    async def ping(self) -> dict[str, Any]:
        try:
            resp = await self._client.get("/api/v1/health")
            return {"reachable": resp.status_code == 200, "status": resp.status_code, "url": self.base_url}
        except httpx.HTTPError as exc:
            return {"reachable": False, "error": exc.__class__.__name__, "url": self.base_url}

    async def aclose(self) -> None:
        await self._client.aclose()
