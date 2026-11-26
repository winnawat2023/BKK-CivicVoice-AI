#!/usr/bin/env python3
"""
Step 4: Evaluate the AI understanding layer (intent / category / district / urgency / RAG routing).

  # rules engine only (offline, instant)
  python scripts/04_eval_classifier.py --mode rules

  # real Typhoon on DGX (set VLLM_URL / VLLM_MODEL in src/backend/.env or pass flags)
  python scripts/04_eval_classifier.py --mode llm --llm-url http://192.168.200.101:8001/v1/chat/completions

  # also score real complaint text from the open data (needs a Traffy CSV with a text column)
  python scripts/04_eval_classifier.py --mode rules --csv opendata/raw/traffy_fondue/traffy_2569.csv --limit 500

  # sanity-check that all 50 district names occur in the real open data
  python scripts/04_eval_classifier.py --check-districts
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "backend"))

from civic.classifier import CivicClassifier  # noqa: E402
from civic.config import Settings  # noqa: E402
from civic.districts import DISTRICTS, canonical_district  # noqa: E402
from civic.llm import LLMClient  # noqa: E402

GOLD = ROOT / "src" / "backend" / "tests" / "data" / "eval_cases.jsonl"
FIELDS = ("intent", "category", "sub_category", "district", "urgency", "inquiry_topic")
TEXT_COLUMNS = ("comment", "description", "detail", "message", "text")

# Traffy "type" values -> our 6 categories (only the unambiguous ones).
TYPE_TO_CATEGORY = {
    "ถนน": "ถนน",
    "ทางเท้า": "ทางเท้า",
    "ผิดกฎจราจร": "ผิดกฎจราจร",
    "ไฟฟ้า": "ไฟฟ้า",
    "ความสะอาด": "ความสะอาด",
}


def load_gold() -> list[dict]:
    return [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_classifier(args) -> tuple[CivicClassifier, LLMClient | None]:
    settings = Settings.from_env()
    if args.llm_url:
        settings = Settings(**{**settings.__dict__, "vllm_url": args.llm_url})
    if args.model:
        settings = Settings(**{**settings.__dict__, "vllm_model": args.model})
    use_llm = args.mode == "llm"
    settings = Settings(**{**settings.__dict__, "llm_enabled": use_llm})
    llm = LLMClient(settings) if use_llm else None
    return CivicClassifier(llm, settings), llm


async def eval_gold(clf: CivicClassifier, cases: list[dict]) -> None:
    totals = {f: [0, 0] for f in FIELDS}
    engines: Counter = Counter()
    misses = []
    latencies = []
    for case in cases:
        t0 = time.perf_counter()
        got = (await clf.classify(case["text"])).model_dump()
        latencies.append(time.perf_counter() - t0)
        engines[got["engine"]] += 1
        for f in FIELDS:
            if f in case:
                totals[f][1] += 1
                if got[f] == case[f]:
                    totals[f][0] += 1
                else:
                    misses.append((case["text"][:50], f, case[f], got[f]))
    print(f"\n== Gold set ({len(cases)} cases) engines={dict(engines)} ==")
    for f, (ok, n) in totals.items():
        if n:
            print(f"  {f:<14} {ok:>3}/{n:<3} {ok / n:6.1%}")
    latencies.sort()
    print(f"  latency p50={latencies[len(latencies) // 2]:.2f}s  max={latencies[-1]:.2f}s")
    if misses:
        print("\n  Misses:")
        for text, f, want, got in misses:
            print(f"   - [{f}] want={want!r} got={got!r}  <- {text}")


async def eval_csv(clf: CivicClassifier, path: Path, limit: int) -> None:
    total = Counter()
    with path.open(encoding="utf-8", errors="ignore", newline="") as fh:
        reader = csv.DictReader(fh)
        text_col = next((c for c in TEXT_COLUMNS if c in (reader.fieldnames or [])), None)
        if not text_col:
            print(f"\n!! {path.name}: no free-text column among {TEXT_COLUMNS} (has {reader.fieldnames}); skipping")
            return
        for row in reader:
            text = (row.get(text_col) or "").strip()
            if len(text) < 8:
                continue
            raw_types = (row.get("type") or "").replace("{", "").replace("}", "").replace('"', "")
            labels = [TYPE_TO_CATEGORY[t.strip()] for t in raw_types.split(",") if t.strip() in TYPE_TO_CATEGORY]
            gold_district = canonical_district(row.get("district"))
            got = await clf.classify(text)
            total["n"] += 1
            if gold_district:
                total["district_n"] += 1
                total["district_ok"] += got.district == gold_district
            if len(labels) == 1:
                total["cat_n"] += 1
                total["cat_ok"] += got.category == labels[0]
            if total["n"] >= limit:
                break
    print(f"\n== Real data {path.name} ({total['n']} rows, text column '{text_col}') ==")
    if total["cat_n"]:
        print(f"  category (5 main types) {total['cat_ok']}/{total['cat_n']} = {total['cat_ok'] / total['cat_n']:.1%}")
    if total["district_n"]:
        print(f"  district               {total['district_ok']}/{total['district_n']} = {total['district_ok'] / total['district_n']:.1%}")


def check_districts() -> None:
    files = list((ROOT / "opendata" / "raw").rglob("*.csv"))
    seen: Counter = Counter()
    unknown: Counter = Counter()
    for path in files:
        with path.open(encoding="utf-8", errors="ignore", newline="") as fh:
            reader = csv.DictReader(fh)
            if "district" not in (reader.fieldnames or []):
                continue
            for row in reader:
                raw = (row.get("district") or "").strip()
                if not raw:
                    continue
                name = canonical_district(raw)
                (seen if name else unknown)[name or raw] += 1
    print(f"\n== District names in open data ({len(files)} csv files scanned) ==")
    print(f"  recognised: {len(seen)}/50 distinct districts, {sum(seen.values())} rows")
    print(f"  never seen in this data: {sorted(set(DISTRICTS) - set(seen)) or 'none'}")
    print(f"  unrecognised values (top 10): {unknown.most_common(10) or 'none'}")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("rules", "llm"), default="rules")
    ap.add_argument("--llm-url")
    ap.add_argument("--model")
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--check-districts", action="store_true")
    args = ap.parse_args()

    if args.check_districts:
        check_districts()
        return
    clf, llm = build_classifier(args)
    try:
        await eval_gold(clf, load_gold())
        if args.csv:
            await eval_csv(clf, args.csv, args.limit)
    finally:
        if llm:
            await llm.aclose()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Thai output on Windows consoles
    asyncio.run(main())
