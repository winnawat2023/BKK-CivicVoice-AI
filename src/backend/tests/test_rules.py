import pytest

from civic import rules
from tests.conftest import FLOOD_TEXT, ID_CARD_TEXT


def test_prd_flood_example():
    r = rules.analyze(FLOOD_TEXT)
    assert r.intent == "complaint"
    assert r.category == "อื่นๆ"
    assert r.sub_category == "ท่อระบายน้ำ/น้ำท่วม"
    assert r.urgency == "high"
    assert r.district == "คลองเตย"
    assert r.location_detail == "ซอยสุขุมวิท 50"


def test_prd_sidewalk_demo_script():
    r = rules.analyze("แจ้งทางเท้าชำรุด มีกระเบื้องแตกหน้าร้านสะดวกซื้อ ปากซอยอารีย์ คนสะดุดล้มบ่อยครับ")
    assert (r.intent, r.category) == ("complaint", "ทางเท้า")
    assert r.district == "พญาไท"
    assert r.location_detail == "ปากซอยอารีย์"


def test_inquiry_id_card():
    r = rules.analyze(ID_CARD_TEXT)
    assert r.intent == "inquiry"
    assert r.inquiry_topic == "id_card"
    assert r.district == "จตุจักร"
    assert r.category is None


@pytest.mark.parametrize(
    "text,category",
    [
        ("ถนนหน้าบ้านเป็นหลุมใหญ่มาก", "ถนน"),
        ("ไฟส่องสว่างหน้าปากซอยดับมาสามวันแล้ว", "ไฟฟ้า"),
        ("ขยะกองเต็มหน้าตลาด เหม็นมาก", "ความสะอาด"),
        ("มีคนจอดรถขวางหน้าบ้านตลอดเลย", "ผิดกฎจราจร"),
        ("มอเตอร์ไซค์ขึ้นทางเท้าบ่อยมาก", "ผิดกฎจราจร"),
        ("ฟุตบาทหน้าโรงเรียนพังเป็นหลุม", "ทางเท้า"),
    ],
)
def test_main_categories(text, category):
    r = rules.analyze(text)
    assert r.intent == "complaint"
    assert r.category == category


@pytest.mark.parametrize(
    "text,sub",
    [
        ("ต้นไม้ล้มขวางถนน", "ต้นไม้"),
        ("ข้างบ้านเปิดเสียงดังทุกคืน", "เสียงรบกวน"),
        ("มีหาบเร่ตั้งกีดขวางทางเดิน", "หาบเร่แผงลอย"),
        ("ไฟไหม้ในซอยช่วยด้วย", "เหตุฉุกเฉิน"),
    ],
)
def test_sub_categories_live_under_other(text, sub):
    r = rules.analyze(text)
    assert r.category == "อื่นๆ"
    assert r.sub_category == sub


def test_urgency_levels():
    assert rules.detect_urgency("ถนนมีหลุม อันตรายมาก") == "high"
    assert rules.detect_urgency("ไฟดับ ไม่รีบครับ เมื่อสะดวก") == "low"
    assert rules.detect_urgency("หลอดไฟหน้าบ้านเสีย") == "medium"


def test_unclear_when_nothing_matches():
    assert rules.analyze("สวัสดีครับ").intent == "unclear"
    assert rules.analyze("").intent == "unclear"


def test_location_never_returns_raw_problem_words():
    assert rules.extract_location("ถนนพัง ช่วยด้วย") == ""
    assert rules.extract_location("ซอยลาดพร้าว 71 มีหลุม") == "ซอยลาดพร้าว 71"


def test_profile_prefers_sub_category():
    assert rules.profile_for("อื่นๆ", "ท่อระบายน้ำ/น้ำท่วม")["sla_days"] == 2
    assert rules.profile_for("ถนน", None)["sla_days"] == 3
    assert rules.profile_for(None, None)["sla_days"] == 7
