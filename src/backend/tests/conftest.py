"""Shared fixtures: an isolated app (in-memory DB) with either no LLM or a scripted fake LLM."""

from __future__ import annotations

import json
from typing import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from civic.app import create_app
from civic.config import Settings
from civic.prompts import CLASSIFY_SYSTEM, RAG_SYSTEM

FLOOD_TEXT = "แถวซอยสุขุมวิท 50 มีท่อระบายน้ำแตก น้ำเอ่อท่วมถนน มอเตอร์ไซค์ล้มไปคันนึงแล้ว อันตรายมาก ช่วยส่งคนมาดูหน่อยครับ"
ID_CARD_TEXT = "สอบถามหน่อยครับ วันเสาร์นี้สำนักงานเขตจตุจักรเปิดทำบัตรประชาชนไหมครับ แล้วต้องเตรียมเอกสารอะไรไปบ้าง"


def base_settings(**overrides) -> Settings:
    values = dict(db_path=":memory:", llm_enabled=False)
    values.update(overrides)
    return Settings(**values)


def fake_llm_transport(
    classify: Callable[[str], str | dict | int] | None = None,
    rag: Callable[[str], str | int] | None = None,
) -> httpx.MockTransport:
    """A vLLM stand-in. Handlers return the assistant text (dict -> JSON) or an int HTTP error code."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "typhoon-8b"}]})
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        user = body["messages"][-1]["content"]
        if system == CLASSIFY_SYSTEM and classify:
            out = classify(user)
        elif system == RAG_SYSTEM and rag:
            out = rag(user)
        else:
            return httpx.Response(500, text="no scripted reply")
        if isinstance(out, int):
            return httpx.Response(out, text="error")
        if isinstance(out, dict):
            out = json.dumps(out, ensure_ascii=False)
        return httpx.Response(200, json={"choices": [{"message": {"content": out}}]})

    return httpx.MockTransport(handler)


@pytest.fixture
def client():
    app = create_app(base_settings())
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_client():
    clients: list[TestClient] = []

    def _make(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> TestClient:
        app = create_app(settings or base_settings(), llm_transport=transport)
        tc = TestClient(app)
        tc.__enter__()
        clients.append(tc)
        return tc

    yield _make
    for tc in clients:
        tc.__exit__(None, None, None)
