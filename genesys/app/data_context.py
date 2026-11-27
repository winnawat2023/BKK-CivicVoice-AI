"""Load small data files from the workspace data/ folder for prompt context."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .config import Settings


def _resolve_data_dir(settings: Settings) -> Path | None:
    raw = (getattr(settings, "data_context_dir", "") or "").strip()
    if raw:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            # relative to genesys/ (app working dir) or repo root
            cand = (Path.cwd() / p).resolve()
            if cand.exists():
                return cand
            cand2 = (Path(__file__).resolve().parents[2] / p).resolve()
            if cand2.exists():
                return cand2
        if p.exists():
            return p.resolve()
        return None

    # Default: <repo>/data
    repo_data = Path(__file__).resolve().parents[2] / "data"
    if repo_data.exists():
        return repo_data
    cwd_data = Path.cwd() / "data"
    if cwd_data.exists():
        return cwd_data.resolve()
    return None


def _iter_files(root: Path) -> Iterable[Path]:
    exts = {".md", ".txt", ".csv", ".json"}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def _summarize_json(path: Path, text: str) -> str:
    try:
        obj = json.loads(text)
    except Exception:
        return text
    if isinstance(obj, list):
        # Keep metadata, drop huge nested blobs where possible.
        sample = []
        for item in obj[:80]:
            if isinstance(item, dict):
                keep = {}
                for k, v in item.items():
                    if k == "resources" and isinstance(v, list):
                        keep[k] = [
                            {rk: rv for rk, rv in r.items() if rk in {"name", "format", "url"}}
                            for r in v[:3]
                            if isinstance(r, dict)
                        ]
                    elif isinstance(v, (str, int, float, bool)) or v is None:
                        keep[k] = v
                    elif isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v[:20]):
                        keep[k] = v[:20]
                sample.append(keep)
            else:
                sample.append(item)
        return json.dumps({"type": "list", "count": len(obj), "sample": sample}, ensure_ascii=False, indent=2)
    if isinstance(obj, dict):
        # Trim very large values.
        trimmed = {}
        for k, v in obj.items():
            s = json.dumps(v, ensure_ascii=False)
            if len(s) > 4000:
                trimmed[k] = f"<trimmed {len(s)} chars>"
            else:
                trimmed[k] = v
        return json.dumps(trimmed, ensure_ascii=False, indent=2)
    return json.dumps(obj, ensure_ascii=False, indent=2)


def load_data_context(settings: Settings, max_chars: int = 40000) -> str:
    if not getattr(settings, "data_context_enabled", False):
        return ""
    root = _resolve_data_dir(settings)
    if root is None:
        return ""

    parts: list[str] = []
    total = 0
    skip_names = {"bkk_catalog_all.json"}

    for path in _iter_files(root):
        if path.name in skip_names:
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if path.suffix.lower() == ".json":
            content = _summarize_json(path, raw)
        else:
            content = raw

        # Per-file cap.
        if len(content) > 12000:
            content = content[:12000] + "\n...[truncated]..."

        rel = path.relative_to(root).as_posix()
        block = f"### FILE: data/{rel}\n{content}\n"
        if total + len(block) > max_chars:
            remaining = max_chars - total
            if remaining > 200:
                parts.append(block[:remaining] + "\n...[truncated]...")
            break
        parts.append(block)
        total += len(block)

    if not parts:
        return ""
    return (
        "## ข้อมูลอ้างอิงจากโฟลเดอร์ data/ (ใช้ประกอบการตอบคำถาม)\n"
        + "\n".join(parts)
    )
