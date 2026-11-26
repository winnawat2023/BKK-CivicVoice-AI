"""Answer citizen questions about BKK services, grounded in the curated dataset.

Order of preference (NFR1: first words within ~2 s):
  1. retrieve -> if nothing relevant: honest "no information" + offer a human transfer (FR5.2)
  2. LLM answer constrained to the retrieved context (short timeout)
  3. extractive answer straight from the best document (also used when the LLM is down or
     produced numbers that are not in the sources)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from ..config import Settings
from ..llm import LLMClient, LLMError
from ..prompts import rag_messages
from .retriever import CivicRetriever

logger = logging.getLogger("bkk-civic-voice.rag")

NO_INFO_TH = (
    "ขออภัยค่ะ ตอนนี้ยังไม่มีข้อมูลเรื่องนี้ในระบบ "
    "ต้องการให้โอนสายหาเจ้าหน้าที่เพื่อสอบถามเพิ่มเติมไหมคะ"
)
_NUMBER = re.compile(r"\d[\d,\.:]*")


@dataclass
class RagAnswer:
    answered: bool
    text: str
    via: Literal["llm", "extractive", "none"]
    score: float = 0.0
    transfer_to_agent: bool = False
    sources: list[dict[str, str]] = field(default_factory=list)


def _number_tokens(text: str) -> set[str]:
    return {t for t in (n.strip(".,:").replace(",", "") for n in _NUMBER.findall(text)) if t}


def _numbers_grounded(reply: str, context: str) -> bool:
    """True when every number in the reply is also a whole number in the sources (blocks invented fees/days)."""
    return _number_tokens(reply) <= _number_tokens(context)


class RagService:
    def __init__(self, retriever: CivicRetriever, llm: LLMClient | None, settings: Settings):
        self._retriever = retriever
        self._llm = llm
        self._settings = settings

    async def answer(self, question: str, *, topic: str | None = None) -> RagAnswer:
        hits = self._retriever.search(question, k=self._settings.rag_top_k, topic=topic)
        usable = [h for h in hits if h.score >= self._settings.rag_min_score]
        if not usable:
            return RagAnswer(False, NO_INFO_TH, "none", score=hits[0].score if hits else 0.0, transfer_to_agent=True)

        best = usable[0]
        sources = [{"id": h.document.id, "title": h.document.title, "source": h.document.source} for h in usable]
        context_blocks = [h.document.context_block() for h in usable]

        if self._settings.rag_use_llm and self._llm is not None and self._settings.llm_enabled:
            try:
                reply = (
                    await self._llm.chat(
                        rag_messages(question, context_blocks),
                        max_tokens=180,
                        temperature=0.1,
                        timeout=self._settings.rag_timeout_s,
                        json_mode=False,
                    )
                ).strip()
                if reply and len(reply) <= 600 and _numbers_grounded(reply, "\n".join(context_blocks)):
                    return RagAnswer(True, reply, "llm", score=best.score, sources=sources)
                logger.info("LLM RAG reply rejected (empty/long/ungrounded), using extractive answer")
            except LLMError as exc:
                logger.warning("LLM RAG unavailable, using extractive answer: %s", exc)

        return RagAnswer(True, best.document.answer, "extractive", score=best.score, sources=sources)
