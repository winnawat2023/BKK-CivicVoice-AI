"""Dependency-free Thai retrieval.

Thai has no spaces between words, so instead of a tokenizer we combine
 (1) curated keyword matches (strong, precise) and
 (2) character-bigram coverage of the question against each document's title/questions/keywords.
This is fast (<5 ms), deterministic and needs no GPU; an embedding reranker can be added later.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DATA = Path(__file__).resolve().parent / "data" / "bkk_regulations.json"

# Fillers that carry no topic information.
_NOISE = (
    "สวัสดีครับ", "สวัสดีค่ะ", "สวัสดี", "ขอสอบถาม", "สอบถาม", "ขอถาม", "อยากทราบ", "อยากถาม",
    "หน่อยครับ", "หน่อยค่ะ", "หน่อย", "ครับ", "ค่ะ", "คะ", "นะคะ", "นะครับ", "นะ", "ด้วย", "ช่วย",
    "ไหม", "บ้าง", "อะไร",
)
_STRIP = re.compile(r"[\s\.,;:!?\"'()\[\]{}\-_/\\]+")


def normalize(text: str) -> str:
    out = (text or "").lower()
    for noise in sorted(_NOISE, key=len, reverse=True):
        out = out.replace(noise, " ")
    return _STRIP.sub("", out)


def bigrams(text: str) -> set[str]:
    return {text[i : i + 2] for i in range(len(text) - 1)}


@dataclass(frozen=True)
class Document:
    id: str
    topic: str
    title: str
    answer: str
    details: str = ""
    keywords: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()
    source: str = ""
    _grams: frozenset[str] = field(default=frozenset(), repr=False, compare=False)

    def context_block(self) -> str:
        parts = [f"หัวข้อ: {self.title}", f"สรุป: {self.answer}"]
        if self.details:
            parts.append(f"รายละเอียด: {self.details}")
        return "\n".join(parts)


@dataclass(frozen=True)
class Hit:
    document: Document
    score: float  # 0..1 confidence used for the answer / no-answer decision
    rank_score: float  # un-capped, used only for ordering


def load_documents(path: str | Path | None = None) -> list[Document]:
    raw = json.loads(Path(path or DEFAULT_DATA).read_text(encoding="utf-8"))
    docs: list[Document] = []
    for item in raw["documents"]:
        focus = normalize(
            " ".join([item["title"], *item.get("questions", []), *item.get("keywords", [])])
        )
        docs.append(
            Document(
                id=item["id"],
                topic=item.get("topic", "other"),
                title=item["title"],
                answer=item["answer"],
                details=item.get("details", ""),
                keywords=tuple(item.get("keywords", [])),
                questions=tuple(item.get("questions", [])),
                source=item.get("source", ""),
                _grams=frozenset(bigrams(focus)),
            )
        )
    return docs


class CivicRetriever:
    def __init__(self, documents: list[Document] | None = None):
        self.documents = documents if documents is not None else load_documents()
        # Keywords shared by many documents ("บัตรประชาชน") say less than specific ones ("บัตรหาย").
        df: dict[str, int] = {}
        for doc in self.documents:
            for kw in {_STRIP.sub("", k.lower()) for k in doc.keywords}:
                df[kw] = df.get(kw, 0) + 1
        self._keywords: dict[str, list[tuple[str, float]]] = {
            doc.id: [
                (kw, len(kw) / (df[kw] ** 0.5))
                for kw in sorted({_STRIP.sub("", k.lower()) for k in doc.keywords})
            ]
            for doc in self.documents
        }

    def search(self, query: str, k: int = 3, *, topic: str | None = None) -> list[Hit]:
        raw_query = (query or "").lower()
        norm = normalize(query)
        if len(norm) < 2:
            return []
        qgrams = bigrams(norm)
        squashed = _STRIP.sub("", raw_query)
        hits: list[Hit] = []
        for doc in self.documents:
            found = [(kw, weight) for kw, weight in self._keywords[doc.id] if kw in squashed]
            # A keyword nested inside another matched keyword is the same words counted twice.
            kw_chars = sum(
                weight for kw, weight in found if not any(kw != other and kw in other for other, _ in found)
            )
            coverage = len(qgrams & doc._grams) / len(qgrams) if qgrams else 0.0
            confidence = 0.7 * min(1.0, kw_chars / 12) + 0.3 * coverage
            rank = kw_chars / 12 + 0.5 * coverage
            if topic and doc.topic == topic:
                rank += 0.25  # prefer the topic the classifier already identified
            hits.append(Hit(doc, round(min(1.0, confidence), 4), rank))
        hits.sort(key=lambda h: h.rank_score, reverse=True)
        return hits[:k]
