import asyncio

import httpx
import pytest

from civic.classifier import CivicClassifier, classify_with_rules, parse_llm_classification
from civic.llm import LLMClient, LLMError, extract_json
from tests.conftest import FLOOD_TEXT, ID_CARD_TEXT, base_settings, fake_llm_transport

GOOD = {
    "intent": "complaint",
    "category": "อื่นๆ",
    "sub_category": "ท่อระบายน้ำ/น้ำท่วม",
    "district": "เขตคลองเตย",
    "location_detail": "ซอยสุขุมวิท 50",
    "urgency": "high",
    "summary": ["ท่อระบายน้ำแตก น้ำท่วมถนน", "ซอยสุขุมวิท 50 เขตคลองเตย", "เร่งด่วนสูง ผู้ขับขี่ล้ม"],
    "inquiry_topic": None,
    "confidence": 0.9,
}


def run(coro):
    return asyncio.run(coro)


def classifier_with(transport) -> tuple[CivicClassifier, LLMClient]:
    settings = base_settings(llm_enabled=True, llm_timeout_s=1.0)
    llm = LLMClient(settings, transport=transport)
    return CivicClassifier(llm, settings), llm


def classify(transport, text):
    clf, llm = classifier_with(transport)

    async def go():
        try:
            return await clf.classify(text)
        finally:
            await llm.aclose()

    return run(go())


# ------------------------------------------------------------ LLM happy path
def test_llm_result_is_used_and_derived_fields_filled():
    c = classify(fake_llm_transport(classify=lambda _: GOOD), FLOOD_TEXT)
    assert c.engine == "llm"
    assert (c.intent, c.category, c.sub_category) == ("complaint", "อื่นๆ", "ท่อระบายน้ำ/น้ำท่วม")
    assert c.district == "คลองเตย"  # "เขต" prefix stripped
    assert c.urgency == "high"
    assert c.estimated_sla_days == 1  # high urgency
    assert "ระบายน้ำ" in c.target_unit
    assert len(c.summary_lines) == 3
    assert not c.needs_location


COMPACT = {"intent": "complaint", "category": None, "sub": "drain", "district": "คลองเตย",
           "urgency": "high"}


def test_compact_code_reply_is_expanded_by_code():
    """The prompt asks for tiny English-code replies (vLLM is slow); code fills in the rest."""
    c = classify(fake_llm_transport(classify=lambda _: COMPACT), FLOOD_TEXT)
    assert c.engine == "llm"
    assert (c.category, c.sub_category) == ("อื่นๆ", "ท่อระบายน้ำ/น้ำท่วม")
    assert c.location_detail == "ซอยสุขุมวิท 50"  # location comes from the rules, not the model
    assert len(c.summary_lines) == 3 and "ระบายน้ำ" in c.target_unit


def test_compact_category_code_and_inquiry_topic():
    c = classify(
        fake_llm_transport(classify=lambda _: {**COMPACT, "category": "electric", "sub": None}),
        "ไฟส่องสว่างเสาไฟหน้าซอยอารีย์ดับ",
    )
    assert c.category == "ไฟฟ้า"
    # The model's (unreliable) topic is ignored: the rules decide it.
    inquiry = {"intent": "inquiry", "category": None, "sub": None, "district": None,
               "urgency": "low", "topic": "elderly_allowance"}
    c2 = classify(fake_llm_transport(classify=lambda _: inquiry), ID_CARD_TEXT)
    assert (c2.intent, c2.inquiry_topic) == ("inquiry", "id_card")
    c3 = classify(fake_llm_transport(classify=lambda _: inquiry), "ขอใบอนุญาตก่อสร้างอาคารสูง")
    assert c3.inquiry_topic == "other"


def test_sub_category_kept_when_rules_agree_even_if_model_gave_a_category():
    # Observed: {"category":"traffic","sub":"tree"} for a fallen tree blocking the road.
    reply = {"intent": "complaint", "category": "traffic", "sub": "tree", "district": "ลาดพร้าว", "urgency": "medium"}
    c = classify(fake_llm_transport(classify=lambda _: reply), "ต้นไม้ใหญ่ล้มขวางถนนหน้าหมู่บ้าน เขตลาดพร้าว")
    assert (c.category, c.sub_category) == ("อื่นๆ", "ต้นไม้")


def test_category_wins_over_a_mixed_up_sub_category():
    # Observed on the real model: {"category":"clean","sub":"dust"} for a garbage complaint.
    reply = {"intent": "complaint", "category": "clean", "sub": "dust", "district": "สาทร", "urgency": "low"}
    c = classify(fake_llm_transport(classify=lambda _: reply), "ขยะกองสูงหน้าตลาด เหม็นมาก เขตสาทร")
    assert (c.category, c.sub_category) == ("ความสะอาด", None)


def test_classify_fast_is_rules_only_and_uses_llm_flag():
    clf, _ = classifier_with(fake_llm_transport(classify=lambda _: COMPACT))
    assert clf.uses_llm is True
    assert CivicClassifier(None, base_settings()).uses_llm is False
    assert clf.classify_fast(FLOOD_TEXT).engine == "rules"


def test_llm_inquiry():
    reply = {
        "intent": "inquiry", "category": None, "district": "จตุจักร", "urgency": "low",
        "summary": ["a", "b", "c"], "inquiry_topic": "id_card", "confidence": 0.95,
    }
    c = classify(fake_llm_transport(classify=lambda _: reply), ID_CARD_TEXT)
    assert (c.intent, c.category, c.inquiry_topic) == ("inquiry", None, "id_card")
    assert c.estimated_sla_days == 0 and c.target_unit == ""


def test_llm_json_wrapped_in_markdown_fence_is_accepted():
    import json

    wrapped = "นี่คือผลลัพธ์\n```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```"
    c = classify(fake_llm_transport(classify=lambda _: wrapped), FLOOD_TEXT)
    assert c.engine == "llm"


# ------------------------------------------------- validation & cross-checks
def test_invalid_district_from_llm_is_replaced_by_rules():
    reply = {**GOOD, "district": "เชียงใหม่"}
    c = classify(fake_llm_transport(classify=lambda _: reply), FLOOD_TEXT)
    assert c.district == "คลองเตย"  # from the Sukhumvit 50 landmark hint


def test_explicit_khet_in_speech_beats_llm_district():
    reply = {**GOOD, "district": "บางรัก"}
    c = classify(fake_llm_transport(classify=lambda _: reply), "ท่อแตกน้ำท่วมซอยหนึ่ง เขตดินแดง อันตรายมาก")
    assert c.district == "ดินแดง"


def test_rules_can_raise_but_not_lower_urgency():
    reply = {**GOOD, "urgency": "low"}
    c = classify(fake_llm_transport(classify=lambda _: reply), FLOOD_TEXT)
    assert c.urgency == "high"  # "อันตราย" / "ล้ม" in the speech
    calm = {**GOOD, "urgency": "high"}
    c2 = classify(fake_llm_transport(classify=lambda _: calm), "หลอดไฟหน้าบ้านดับ เขตดินแดง")
    assert c2.urgency == "high"  # the model's call is never lowered


def test_missing_or_short_summary_is_rebuilt_to_three_lines():
    reply = {**GOOD, "summary": ["only one line"]}
    c = classify(fake_llm_transport(classify=lambda _: reply), FLOOD_TEXT)
    assert len(c.summary_lines) == 3
    assert all(c.summary_lines)


def test_unknown_category_falls_back_to_rules_category():
    reply = {**GOOD, "category": "อะไรก็ไม่รู้", "sub_category": None}
    c = classify(fake_llm_transport(classify=lambda _: reply), "ไฟส่องสว่างเสาไฟหน้าซอยอารีย์ดับ")
    assert c.engine == "llm" and c.category == "ไฟฟ้า"


def test_raw_transcript_is_never_kept_as_location():
    reply = {**GOOD, "location_detail": FLOOD_TEXT}
    c = classify(fake_llm_transport(classify=lambda _: reply), FLOOD_TEXT)
    assert c.location_detail == "ซอยสุขุมวิท 50"


# --------------------------------------------------------- failure fallbacks
@pytest.mark.parametrize(
    "transport",
    [
        fake_llm_transport(classify=lambda _: 500),
        fake_llm_transport(classify=lambda _: "ขอโทษครับ ตอบไม่ได้"),
        fake_llm_transport(classify=lambda _: "{ not json"),
        fake_llm_transport(classify=lambda _: {"intent": "dance"}),
    ],
    ids=["http-500", "prose", "bad-json", "bad-intent"],
)
def test_bad_llm_output_falls_back_to_rules(transport):
    c = classify(transport, "ไฟส่องสว่างหน้าบ้านดับมาสองวัน เขตดินแดง")
    assert c.engine == "rules"
    assert (c.intent, c.category, c.district) == ("complaint", "ไฟฟ้า", "ดินแดง")


def test_complaint_with_no_category_anywhere_is_malformed_and_falls_back():
    # FR7.2: output that cannot be validated counts as "not understood"
    c = classify(
        fake_llm_transport(classify=lambda _: {"intent": "complaint", "category": None}),
        "สวัสดีครับ",
    )
    assert c.engine == "rules"
    assert c.intent == "unclear" and c.understood is False


def test_unreachable_llm_falls_back_to_rules():
    def boom(request):
        raise httpx.ConnectError("refused")

    c = classify(httpx.MockTransport(boom), FLOOD_TEXT)
    assert c.engine == "rules"
    assert c.sub_category == "ท่อระบายน้ำ/น้ำท่วม" and c.urgency == "high"


def test_llm_disabled_uses_rules_only():
    clf = CivicClassifier(None, base_settings())
    c = run(clf.classify(FLOOD_TEXT))
    assert c.engine == "rules"


def test_empty_text_is_unclear_and_not_understood():
    c = classify_with_rules("")
    assert c.intent == "unclear" and c.understood is False
    assert len(c.summary_lines) == 3


def test_complaint_without_any_location_asks_for_location():
    c = classify_with_rules("ท่อน้ำแตกน้ำท่วมถนนช่วยด้วย")
    assert c.intent == "complaint" and c.needs_location is True


def test_rules_summary_has_three_lines_and_no_raw_transcript():
    c = classify_with_rules(FLOOD_TEXT)
    assert len(c.summary_lines) == 3
    assert FLOOD_TEXT not in c.summary_th
    assert "คลองเตย" in c.summary_lines[1]


def test_parse_rejects_unknown_intent():
    with pytest.raises(LLMError):
        parse_llm_classification({"intent": "x"}, "ข้อความ")


def test_extract_json_errors():
    with pytest.raises(LLMError):
        extract_json("")
    with pytest.raises(LLMError):
        extract_json("[1,2,3]")
