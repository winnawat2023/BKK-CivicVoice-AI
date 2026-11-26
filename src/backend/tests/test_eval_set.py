"""Regression guard: the rules engine (the offline fallback) must stay accurate on the gold set."""

import json
from pathlib import Path

from civic.classifier import classify_with_rules

CASES = [
    json.loads(line)
    for line in (Path(__file__).parent / "data" / "eval_cases.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
FIELDS = ("intent", "category", "sub_category", "district", "urgency", "inquiry_topic")


def score(cases):
    totals = {f: [0, 0] for f in FIELDS}
    misses = []
    for case in cases:
        got = classify_with_rules(case["text"]).model_dump()
        for f in FIELDS:
            if f in case:
                totals[f][1] += 1
                if got[f] == case[f]:
                    totals[f][0] += 1
                else:
                    misses.append((case["text"][:40], f, case[f], got[f]))
    return totals, misses


def test_gold_set_is_not_trivial():
    assert len(CASES) >= 25
    assert {c["intent"] for c in CASES} == {"complaint", "inquiry", "unclear"}


def test_rules_engine_accuracy_on_gold_set():
    totals, misses = score(CASES)
    report = {f: f"{ok}/{n}" for f, (ok, n) in totals.items()}
    for field, floor in {"intent": 0.95, "category": 0.9, "district": 0.95, "urgency": 0.9, "inquiry_topic": 0.9}.items():
        ok, n = totals[field]
        assert n and ok / n >= floor, f"{field} accuracy {ok}/{n} below {floor}: {report}\nmisses: {misses}"
