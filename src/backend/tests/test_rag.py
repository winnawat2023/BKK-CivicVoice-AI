import asyncio

import httpx
import pytest

from civic.llm import LLMClient
from civic.rag import CivicRetriever, RagService, load_documents
from civic.rag.service import NO_INFO_TH, _numbers_grounded
from tests.conftest import base_settings, fake_llm_transport


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def retriever():
    return CivicRetriever()


def test_dataset_covers_the_three_required_topics():
    topics = {d.topic for d in load_documents()}
    assert {"id_card", "house_registration", "elderly_allowance"} <= topics
    for doc in load_documents():
        assert doc.answer and doc.title and doc.keywords


@pytest.mark.parametrize(
    "question,expected_id",
    [
        ("วันเสาร์นี้สำนักงานเขตเปิดทำบัตรประชาชนไหมครับ", "id_card_hours"),
        ("บัตรประชาชนหายต้องทำยังไง เสียเงินไหม", "id_card_lost"),
        ("บัตรประชาชนหมดอายุแล้วต้องทำใหม่ใช้เอกสารอะไร", "id_card_renew"),
        ("ลูกอายุครบ 7 ปี ต้องทำบัตรประชาชนครั้งแรกไหม", "id_card_first_time"),
        ("อยากย้ายทะเบียนบ้านเข้าต้องใช้เอกสารอะไร", "house_move"),
        ("แจ้งเกิดลูกต้องทำภายในกี่วัน", "house_birth"),
        ("คนในบ้านเสียชีวิต ต้องแจ้งตายกี่ชั่วโมง", "house_death"),
        ("เบี้ยยังชีพผู้สูงอายุอายุ 70 ปีได้เดือนละเท่าไหร่", "elderly_rate"),
        ("ใครมีสิทธิรับเบี้ยผู้สูงอายุบ้าง", "elderly_eligibility"),
        ("ลงทะเบียนเบี้ยยังชีพคนชราที่ไหน ใช้เอกสารอะไร", "elderly_register"),
        ("สายด่วน 1555 เปิดกี่โมง", "hotline_1555"),
    ],
)
def test_retrieval_picks_the_right_document(retriever, question, expected_id):
    hits = retriever.search(question, k=3)
    assert hits[0].document.id == expected_id, [h.document.id for h in hits]
    assert hits[0].score >= 0.22


@pytest.mark.parametrize(
    "question",
    [
        "ขอใบอนุญาตก่อสร้างอาคารสูงต้องทำอย่างไร",
        "วันนี้อากาศเป็นอย่างไรบ้าง",
        "สวัสดีครับ",
        "",
    ],
)
def test_out_of_scope_questions_score_below_threshold(retriever, question):
    hits = retriever.search(question, k=1)
    assert not hits or hits[0].score < base_settings().rag_min_score


def test_no_information_answer_offers_transfer(retriever):
    svc = RagService(retriever, None, base_settings())
    ans = run(svc.answer("ขอใบอนุญาตก่อสร้างอาคารสูงต้องทำอย่างไร"))
    assert not ans.answered and ans.transfer_to_agent
    assert ans.text == NO_INFO_TH and ans.via == "none"


def test_extractive_answer_when_llm_disabled(retriever):
    svc = RagService(retriever, None, base_settings())
    ans = run(svc.answer("เบี้ยยังชีพผู้สูงอายุอายุ 70 ปีได้เดือนละเท่าไหร่"))
    assert ans.answered and ans.via == "extractive"
    assert "700" in ans.text
    assert ans.sources and ans.sources[0]["id"] == "elderly_rate"


def _service(retriever, transport):
    settings = base_settings(llm_enabled=True, rag_use_llm=True, rag_timeout_s=1.0)
    llm = LLMClient(settings, transport=transport)
    return RagService(retriever, llm, settings), llm


def test_llm_answer_is_used_when_grounded(retriever):
    reply = "อายุ 70 ถึง 79 ปี ได้รับเดือนละ 700 บาทค่ะ"
    svc, llm = _service(retriever, fake_llm_transport(rag=lambda _: reply))

    async def go():
        try:
            return await svc.answer("เบี้ยยังชีพผู้สูงอายุอายุ 70 ปีได้เดือนละเท่าไหร่")
        finally:
            await llm.aclose()

    ans = run(go())
    assert ans.via == "llm" and ans.text == reply


def test_llm_answer_with_invented_numbers_is_rejected(retriever):
    svc, llm = _service(retriever, fake_llm_transport(rag=lambda _: "ได้เดือนละ 5,000 บาทค่ะ"))

    async def go():
        try:
            return await svc.answer("เบี้ยยังชีพผู้สูงอายุอายุ 70 ปีได้เดือนละเท่าไหร่")
        finally:
            await llm.aclose()

    ans = run(go())
    assert ans.via == "extractive" and "5,000" not in ans.text


@pytest.mark.parametrize("failure", [500, ""], ids=["http-500", "empty"])
def test_llm_failure_falls_back_to_extractive(retriever, failure):
    svc, llm = _service(retriever, fake_llm_transport(rag=lambda _: failure))

    async def go():
        try:
            return await svc.answer("แจ้งเกิดลูกต้องทำภายในกี่วัน")
        finally:
            await llm.aclose()

    ans = run(go())
    assert ans.answered and ans.via == "extractive" and "15 วัน" in ans.text


def test_llm_timeout_falls_back_to_extractive(retriever):
    def slow(request):
        raise httpx.ReadTimeout("slow")

    svc, llm = _service(retriever, httpx.MockTransport(slow))

    async def go():
        try:
            return await svc.answer("แจ้งตายต้องแจ้งภายในกี่ชั่วโมง")
        finally:
            await llm.aclose()

    ans = run(go())
    assert ans.via == "extractive" and "24" in ans.text


def test_numbers_grounded_helper():
    ctx = "ภายใน 15 วัน ค่าธรรมเนียม 100 บาท เวลา 08:30 อัตรา 1,000 บาท"
    assert _numbers_grounded("ภายใน 15 วันค่ะ", ctx)
    assert _numbers_grounded("เวลา 08:30 น. และ 1,000 บาท", ctx)
    assert not _numbers_grounded("ภายใน 30 วันค่ะ", ctx)
    assert _numbers_grounded("ไม่มีตัวเลข", ctx)
