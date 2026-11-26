"""Async client for the Thai LLM served by vLLM (OpenAI-compatible ``/v1/chat/completions``).

Model on DGX: ``typhoon-8b`` (scb10x/llama-3-typhoon-v1.5-8b-instruct, 8192 context).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger("bkk-civic-voice.llm")


class LLMError(Exception):
    """The LLM was unreachable, too slow, or returned something unusable."""


class LLMClient:
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self._settings = settings
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self._settings.vllm_api_key:
                headers["Authorization"] = f"Bearer {self._settings.vllm_api_key}"
            self._client = httpx.AsyncClient(headers=headers, transport=self._transport)
        return self._client

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 300,
        temperature: float = 0.0,
        timeout: float | None = None,
        json_mode: bool | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": self._settings.vllm_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode if json_mode is not None else self._settings.llm_json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            resp = await self._http().post(
                self._settings.vllm_url,
                json=body,
                timeout=timeout if timeout is not None else self._settings.llm_timeout_s,
            )
        except httpx.HTTPError as exc:  # timeouts, connection errors
            raise LLMError(f"LLM request failed: {type(exc).__name__}: {exc}") from exc
        if resp.status_code != 200:
            raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected LLM response shape: {exc}") from exc

    async def ping(self, timeout: float = 3.0) -> dict[str, Any]:
        """Cheap reachability check: GET <vllm base>/v1/models."""
        url = self._settings.vllm_url.split("/chat/completions")[0].rstrip("/") + "/models"
        try:
            resp = await self._http().get(url, timeout=timeout)
            resp.raise_for_status()
            models = [m.get("id") for m in resp.json().get("data", [])]
            return {"reachable": True, "models": models, "url": url}
        except Exception as exc:
            return {"reachable": False, "error": f"{type(exc).__name__}: {exc}", "url": url}

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM reply (handles code fences and chatter)."""
    if not text:
        raise LLMError("Empty LLM reply")
    candidate = text
    fenced = _FENCE.search(text)
    if fenced:
        candidate = fenced.group(1)
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        raise LLMError("No JSON object in LLM reply")
    try:
        data = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"Invalid JSON from LLM: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("LLM JSON is not an object")
    return data
