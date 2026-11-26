"""Understand one caller utterance: intent, problem category, district (of 50) and urgency.

Pipeline: Thai LLM (Typhoon) -> strict validation -> cross-check with the rules engine.
If the LLM is down, slow, or returns malformed output the rules engine answers instead, so a
call never dies on an AI hiccup (the result is tagged ``engine="rules"``).
"""

from __future__ import annotations

import logging
from typing import Any

from . import rules
from .config import Settings
from .districts import canonical_district, extract_explicit_district
from .llm import LLMClient, LLMError, extract_json
from .prompts import classify_messages
from .schemas import (
    CATEGORIES,
    CATEGORY_CODES,
    SUB_CATEGORY_CODES,
    SUB_CATEGORY_PROFILE,
    URGENCY_LEVELS,
    URGENCY_TH,
    Classification,
)

logger = logging.getLogger("bkk-civic-voice.classifier")

_URGENCY_RANK = {"low": 0, "medium": 1, "high": 2}
_INTENTS = ("complaint", "inquiry", "unclear")


def _clean_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _valid_summary(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    lines = [_clean_str(v) for v in value if _clean_str(v)]
    if len(lines) < 3:
        return None
    return [line[:140] for line in lines[:3]]


def build_summary_lines(c: Classification) -> list[str]:
    """3-line Thai summary used when the LLM did not supply a valid one."""
    if c.intent == "inquiry":
        topic = rules.TOPIC_TH.get(c.inquiry_topic or "other", rules.TOPIC_TH["other"])
        where = f"สำนักงานเขต{c.district}" if c.district else "ไม่ระบุเขต"
        return [f"ประชาชนสอบถาม: {topic}", f"พื้นที่: {where}", "ตอบจากข้อมูลระเบียบ กทม. อัตโนมัติ"]
    if c.intent == "unclear":
        return ["ระบบจับใจความคำพูดไม่ได้", "สถานที่: ไม่ระบุ", "ควรโอนสายหาเจ้าหน้าที่"]
    problem = c.sub_category or c.category or "อื่นๆ"
    place_parts = [p for p in (c.location_detail, f"เขต{c.district}" if c.district else "") if p]
    place = " ".join(place_parts) if place_parts else "ยังไม่ระบุสถานที่ (ควรถามกลับ)"
    return [
        f"แจ้งปัญหา: {problem}",
        f"สถานที่: {place}",
        f"ความเร่งด่วน: {URGENCY_TH[c.urgency]} (SLA คาดการณ์ {c.estimated_sla_days} วัน)",
    ]


def _finalize(c: Classification, *, llm_summary: list[str] | None) -> Classification:
    """Fill the derived fields (SLA, unit, action, flags, summary) from the core fields."""
    if c.intent == "complaint":
        prof = rules.profile_for(c.category, c.sub_category)
        c.estimated_sla_days = 1 if c.urgency == "high" else int(prof["sla_days"])
        c.target_unit = prof["unit"]
        c.suggested_action = prof["action"]
        c.needs_location = not c.district and not c.location_detail
        c.understood = True
    elif c.intent == "inquiry":
        c.estimated_sla_days = 0
        c.target_unit = ""
        c.suggested_action = "ตอบข้อมูลระเบียบ กทม. อัตโนมัติ (ไม่ต้องส่งต่อเขต)"
        c.category = None
        c.sub_category = None
        c.needs_location = False
        c.understood = True
    else:
        c.estimated_sla_days = 0
        c.suggested_action = "โอนสายหาเจ้าหน้าที่"
        c.understood = False
        c.needs_location = False
    c.summary_lines = llm_summary or build_summary_lines(c)
    return c


def classify_with_rules(transcript: str) -> Classification:
    r = rules.analyze(transcript)
    c = Classification(
        intent=r.intent,  # type: ignore[arg-type]
        category=r.category,
        sub_category=r.sub_category,
        district=r.district,
        location_detail=r.location_detail,
        urgency=r.urgency,  # type: ignore[arg-type]
        inquiry_topic=r.inquiry_topic,
        confidence=0.6 if r.intent != "unclear" else 0.2,
        engine="rules",
    )
    return _finalize(c, llm_summary=None)


def parse_llm_classification(data: dict[str, Any], transcript: str) -> Classification:
    """Validate the LLM JSON and merge it with rule-based cross-checks. Raises LLMError if unusable."""
    intent = _clean_str(data.get("intent")).lower()
    if intent not in _INTENTS:
        raise LLMError(f"Invalid intent from LLM: {data.get('intent')!r}")

    urgency = _clean_str(data.get("urgency")).lower()
    if urgency not in URGENCY_LEVELS:
        urgency = "medium"

    # The prompt asks for short codes (road, drain, ...); Thai names are accepted too.
    raw_category = _clean_str(data.get("category"))
    category = CATEGORY_CODES.get(raw_category.lower(), raw_category) or None
    if category not in CATEGORIES:
        category = None
    raw_sub = _clean_str(data.get("sub_category", data.get("sub")))
    sub_category = SUB_CATEGORY_CODES.get(raw_sub.lower(), raw_sub) or None
    if sub_category not in SUB_CATEGORY_PROFILE:
        sub_category = None

    rule = rules.analyze(transcript)

    if intent == "complaint":
        if category is None and sub_category is not None:
            category = "อื่นๆ"  # sub types (drain, tree, ...) all live under "อื่นๆ"
        if category not in (None, "อื่นๆ") and sub_category is not None:
            # Category and sub-type are exclusive (sub-types live under "อื่นๆ") but the 8B model mixes
            # them up (e.g. clean+dust for garbage, traffic+tree for a fallen tree). Let the rules
            # break the tie: keep the sub-type only if they independently found the same one.
            if rule.sub_category == sub_category:
                category = "อื่นๆ"
            else:
                sub_category = None
        if category is None:
            # No usable category from the LLM -> not a valid structured output (FR7.2).
            if rule.category is None:
                raise LLMError("Complaint without a valid category")
            category, sub_category = rule.category, rule.sub_category

    # District: an explicit "เขต<name>" in the speech beats the model; otherwise trust a valid LLM
    # value, then fall back to the rules (district name / landmark hint).
    district = (
        extract_explicit_district(transcript)
        or canonical_district(_clean_str(data.get("district")))
        or rule.district
    )

    location_detail = _clean_str(data.get("location_detail"))
    if len(location_detail) > 60 or location_detail == transcript.strip():
        # A "location" this long is the model echoing the speech; never keep the transcript (FR2.5).
        location_detail = rule.location_detail
    location_detail = location_detail or rule.location_detail

    # Safety net: obvious danger words from the rules can raise, never lower, the urgency.
    if intent == "complaint" and _URGENCY_RANK[rule.urgency] > _URGENCY_RANK[urgency]:
        urgency = rule.urgency

    try:  # heuristic only: the compact prompt does not ask the model for a confidence
        confidence = float(data.get("confidence", 0.8))
    except (TypeError, ValueError):
        confidence = 0.8
    confidence = min(1.0, max(0.0, confidence))

    # The topic is decided by the keyword rules only: the 8B model got it right 4/7 times on the gold
    # set (rules 7/7), so the prompt no longer asks for it. Unknown topics get "other" (RAG then
    # searches everything and, below the confidence threshold, transfers to a human).
    topic = (rule.inquiry_topic or "other") if intent == "inquiry" else None

    c = Classification(
        intent=intent,  # type: ignore[arg-type]
        category=category if intent == "complaint" else None,
        sub_category=sub_category if intent == "complaint" else None,
        district=district,
        location_detail=location_detail if intent == "complaint" else "",
        urgency=urgency if intent == "complaint" else "low",  # type: ignore[arg-type]
        inquiry_topic=topic if intent == "inquiry" else None,
        confidence=confidence,
        engine="llm",
    )
    return _finalize(c, llm_summary=_valid_summary(data.get("summary")))


class CivicClassifier:
    def __init__(self, llm: LLMClient | None, settings: Settings):
        self._llm = llm
        self._settings = settings

    @property
    def uses_llm(self) -> bool:
        return self._llm is not None and self._settings.llm_enabled

    @staticmethod
    def classify_fast(transcript: str) -> Classification:
        """Instant (<1 ms) rules-only result, used for the widget's provisional summary."""
        return classify_with_rules((transcript or "").strip())

    async def classify(self, transcript: str) -> Classification:
        text = (transcript or "").strip()
        if not text:
            return classify_with_rules("")
        if self._llm is not None and self._settings.llm_enabled:
            try:
                raw = await self._llm.chat(
                    classify_messages(text), max_tokens=100, temperature=0.0
                )
                return parse_llm_classification(extract_json(raw), text)
            except LLMError as exc:
                logger.warning("LLM classification unavailable, using rules engine: %s", exc)
            except Exception:  # never let an unexpected error kill the call
                logger.exception("Unexpected classifier error, using rules engine")
        return classify_with_rules(text)
