"""The 50 Bangkok district offices (สำนักงานเขต) and helpers to find one in Thai speech text."""

from __future__ import annotations

import re

DISTRICTS: tuple[str, ...] = (
    "พระนคร", "ดุสิต", "หนองจอก", "บางรัก", "บางเขน",
    "บางกะปิ", "ปทุมวัน", "ป้อมปราบศัตรูพ่าย", "พระโขนง", "มีนบุรี",
    "ลาดกระบัง", "ยานนาวา", "สัมพันธวงศ์", "พญาไท", "ธนบุรี",
    "บางกอกใหญ่", "ห้วยขวาง", "คลองสาน", "ตลิ่งชัน", "บางกอกน้อย",
    "บางขุนเทียน", "ภาษีเจริญ", "หนองแขม", "ราษฎร์บูรณะ", "บางพลัด",
    "ดินแดง", "บึงกุ่ม", "สาทร", "บางซื่อ", "จตุจักร",
    "บางคอแหลม", "ประเวศ", "คลองเตย", "สวนหลวง", "จอมทอง",
    "ดอนเมือง", "ราชเทวี", "ลาดพร้าว", "วัฒนา", "บางแค",
    "หลักสี่", "สายไหม", "คันนายาว", "สะพานสูง", "วังทองหลาง",
    "คลองสามวา", "บางนา", "ทวีวัฒนา", "ทุ่งครุ", "บางบอน",
)

# Common short forms people use when speaking.
ALIASES: dict[str, str] = {
    "ป้อมปราบ": "ป้อมปราบศัตรูพ่าย",
    "ป้อมปราบฯ": "ป้อมปราบศัตรูพ่าย",
    "ราชบูรณะ": "ราษฎร์บูรณะ",
}

# Landmark / road -> district hints. Used ONLY when the caller names no district.
# These are demo-level hints (assumption, to be reviewed), not a geocoder.
LANDMARK_HINTS: dict[str, str] = {
    "สุขุมวิท 50": "คลองเตย",
    "สุขุมวิท50": "คลองเตย",
    "อารีย์": "พญาไท",
    "สนามเป้า": "พญาไท",
    "สยามสแควร์": "ปทุมวัน",
    "จุฬาลงกรณ์": "ปทุมวัน",
    "ข้าวสาร": "พระนคร",
    "เยาวราช": "สัมพันธวงศ์",
    "สีลม": "บางรัก",
    "อโศก": "วัฒนา",
    "ทองหล่อ": "วัฒนา",
    "เอกมัย": "วัฒนา",
    "สะพานควาย": "พญาไท",
}

_ALL_NAMES: dict[str, str] = {name: name for name in DISTRICTS}
_ALL_NAMES.update(ALIASES)

# Longest names first so "ทวีวัฒนา" is tried before "วัฒนา".
_NAMES_BY_LENGTH = sorted(_ALL_NAMES, key=len, reverse=True)
_KHET_PREFIX = re.compile(r"(?:สำนักงานเขต|เขต)\s*$")
_WS = re.compile(r"\s+")


def _squash(text: str) -> str:
    return _WS.sub("", text or "")


def canonical_district(value: str | None) -> str | None:
    """Map an LLM/user supplied value ("เขตคลองเตย", " คลองเตย ") to a canonical district name."""
    if not value:
        return None
    cleaned = _squash(str(value))
    for prefix in ("สำนักงานเขต", "เขต"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    cleaned = cleaned.strip(" .,;:()\"'")
    if cleaned in _ALL_NAMES:
        return _ALL_NAMES[cleaned]
    return None


def _find_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for name in _NAMES_BY_LENGTH:
        start = 0
        while True:
            idx = text.find(name, start)
            if idx < 0:
                break
            spans.append((idx, idx + len(name), _ALL_NAMES[name]))
            start = idx + 1
    # Drop spans fully covered by a longer span (e.g. "วัฒนา" inside "ทวีวัฒนา").
    kept = [
        s
        for s in spans
        if not any(o is not s and o[0] <= s[0] and s[1] <= o[1] and (o[1] - o[0]) > (s[1] - s[0]) for o in spans)
    ]
    return sorted(kept, key=lambda s: s[0])


def extract_explicit_district(text: str) -> str | None:
    """Only a district introduced by the word "เขต" (e.g. "เขตจตุจักร"); road names do not count."""
    squashed = _squash(text)
    for start, _end, district in _find_spans(squashed):
        if _KHET_PREFIX.search(squashed[max(0, start - 12):start]):
            return district
    return None


def extract_district(text: str, *, use_landmarks: bool = True) -> str | None:
    """Find the district a caller mentions.

    Priority: an explicit "เขต<name>" mention, then the first district name, then a landmark hint.
    """
    squashed = _squash(text)
    if not squashed:
        return None
    explicit = extract_explicit_district(text)
    if explicit:
        return explicit
    spans = _find_spans(squashed)
    if spans:
        return spans[0][2]
    if use_landmarks:
        for landmark, district in LANDMARK_HINTS.items():
            if _squash(landmark) in squashed:
                return district
    return None
