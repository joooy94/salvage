"""Case matching agent backed by Wiki pages when available."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from src.wiki_loader import load_all_pages
except Exception:
    load_all_pages = None


def _wiki_root(state: Dict[str, Any]) -> Path:
    return Path(state.get("wiki_dir") or "wiki")


def _read_text(path: Path, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except OSError:
        return ""


def _load_case_entries(root: Path) -> List[Dict[str, Any]]:
    manifest = root / "cases" / "case_manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            pass

    cases_dir = root / "cases"
    if not cases_dir.exists():
        return []
    return [
        {
            "case_no": f"{idx:02d}",
            "title": path.stem,
            "wiki_file": str(path),
            "source_pdf": "钻具断落事故.pdf",
        }
        for idx, path in enumerate(sorted(cases_dir.glob("*.md")), start=1)
    ]


def _load_case_entries_from_loader(root: Path) -> List[Dict[str, Any]]:
    if load_all_pages is None:
        return []
    try:
        pages = load_all_pages(root)
    except Exception:
        return []
    entries = []
    for idx, page in enumerate((item for item in pages if "cases/" in item.relative_path), start=1):
        if page.path.name == "case_manifest.json":
            continue
        entries.append(
            {
                "case_no": page.metadata.get("case_no") or f"{idx:02d}",
                "title": page.title,
                "wiki_file": page.relative_path,
                "source_pdf": page.metadata.get("source_pdf", "钻具断落事故.pdf"),
                "source_pages": page.metadata.get("source_pages") or [],
                "_content": page.content,
            }
        )
    return entries


WEIGHTED_TOKENS: dict[str, int] = {
    "水平井": 8,
    "大斜度": 6,
    "定向井": 6,
    "直井": 5,
    "钻杆": 5,
    "钻铤": 5,
    "油管": 4,
    "接头": 4,
    "卡钻": 5,
    "砂埋": 6,
    "沉砂": 5,
    "断落": 4,
    "鱼顶": 3,
    "打捞": 2,
    "震击": 3,
    "套铣": 4,
    "磨铣": 4,
    "冲砂": 4,
    "倒扣": 3,
}


def _tokens(text: str) -> Iterable[str]:
    for token in WEIGHTED_TOKENS:
        if token in text:
            yield token


def _depths(text: str) -> list[float]:
    values = []
    for raw in re.findall(r"([0-9]{3,5}(?:\.[0-9]+)?)\s*(?:m|米)", text, flags=re.IGNORECASE):
        try:
            value = float(raw)
        except ValueError:
            continue
        if 100 <= value <= 9000:
            values.append(value)
    return values


def _depth_score(accident_depth: Optional[float], case_text: str) -> int:
    if not accident_depth:
        return 0
    depths = _depths(case_text)
    if not depths:
        return 0
    nearest = min(abs(value - accident_depth) for value in depths)
    if nearest <= 100:
        return 10
    if nearest <= 300:
        return 7
    if nearest <= 600:
        return 4
    if nearest <= 1000:
        return 2
    return 0


def _case_score(query_tokens: set[str], query: str, accident_depth: Optional[float], case_text: str, title: str) -> tuple[int, list[str]]:
    haystack = f"{title}\n{case_text}"
    matched = query_tokens & set(_tokens(haystack))
    score = sum(WEIGHTED_TOKENS[token] for token in matched)
    reasons = [f"{token}匹配" for token in sorted(matched)]

    depth_points = _depth_score(accident_depth, haystack)
    if depth_points:
        score += depth_points
        reasons.append(f"深度相近+{depth_points}")

    if "水平井" in query and "水平井" not in haystack:
        score -= 3
        reasons.append("井型差异")
    if "砂埋" in query and not any(term in haystack for term in ["砂埋", "沉砂", "冲砂", "返砂"]):
        score -= 2
        reasons.append("砂埋信息缺失")

    process_terms = ["震击", "套铣", "磨铣", "倒扣", "卡瓦打捞筒", "母锥", "公锥", "反循环"]
    process_hits = [term for term in process_terms if term in haystack]
    if process_hits:
        score += min(6, len(process_hits))
        reasons.append("处置路径丰富")

    return max(0, score), reasons[:6]


def _case_summary(text: str) -> str:
    wanted = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- 事故发生层位/深度") or stripped.startswith("- 落鱼描述") or stripped.startswith("- 最终结果"):
            wanted.append(stripped)
        if len(wanted) >= 3:
            break
    return "；".join(wanted) if wanted else (text.splitlines()[0] if text else "案例页存在但暂未读取到摘要。")


def case_matcher_node(state: Dict[str, Any]) -> Dict[str, Any]:
    accident = state.get("accident", {})
    query = " ".join(str(v) for v in accident.values() if isinstance(v, (str, int, float)))
    query_tokens = set(_tokens(query))
    accident_depth = accident.get("depth")
    root = _wiki_root(state)
    entries = _load_case_entries_from_loader(root) or _load_case_entries(root)

    ranked = []
    for entry in entries:
        wiki_file = Path(entry.get("wiki_file", ""))
        if not wiki_file.is_absolute():
            wiki_file = Path.cwd() / wiki_file
        text = entry.get("_content") or _read_text(wiki_file)
        score, reasons = _case_score(query_tokens, query, accident_depth, text, entry.get("title", ""))
        ranked.append((score, reasons, entry, text))
    ranked.sort(key=lambda item: item[0], reverse=True)

    selected = []
    evidence = list(state.get("evidence", []))
    for score, reasons, entry, text in ranked[:3]:
        source_page = entry.get("wiki_file", "")
        source_pages = entry.get("source_pages") or []
        selected.append(
            {
                "case_no": entry.get("case_no"),
                "title": entry.get("title") or Path(source_page).stem,
                "score": score,
                "reasons": reasons,
                "source_page": source_page,
                "summary": _case_summary(text),
            }
        )
        evidence.append(
            {
                "source_type": "case",
                "source_page": source_page,
                "source_pdf": entry.get("source_pdf", "钻具断落事故.pdf"),
                "page_no": source_pages[0] if source_pages else None,
                "clause": None,
                "quote": "",
                "summary": f"相似案例候选：{entry.get('title') or Path(source_page).stem}（{'; '.join(reasons) or '综合特征匹配'}）",
            }
        )

    if selected:
        similar_cases = "\n".join(
            f"- {item['title']}：匹配分 {item['score']}，依据：{'; '.join(item['reasons']) or '综合特征匹配'}，来源 {item['source_page']}"
            for item in selected
        )
    else:
        similar_cases = "当前 Wiki 案例库不可用或尚未构建，案例匹配以工程推断占位。"
        evidence.append(
            {
                "source_type": "inference",
                "source_page": "",
                "source_pdf": "",
                "page_no": None,
                "clause": None,
                "quote": "",
                "summary": "未找到可读取的案例 Manifest 或案例页。",
            }
        )

    return {**state, "similar_case_items": selected, "similar_cases": similar_cases, "evidence": evidence}
