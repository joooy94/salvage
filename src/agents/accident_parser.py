"""Accident parsing agent.

The first version deliberately favors deterministic extraction over an LLM
call, so the service remains runnable before model credentials are configured.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

try:
    from src.llm_client import try_complete_json
except Exception:
    try_complete_json = None


FIELD_LABELS = {
    "well_type": "井型",
    "depth": "鱼顶深度/事故深度",
    "fish_type": "落鱼类型",
    "fish_description": "落鱼描述",
    "mud_type": "钻井液/井液",
    "inclination": "井斜角",
    "thread_type": "扣型",
}


def _first_match(patterns: List[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" ：:，,。；;")
    return ""


def _extract_depth(text: str) -> float | None:
    patterns = [
        r"(?:鱼顶|井深|深度|卡点|事故位置)[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)",
        r"([0-9]+(?:\.[0-9]+)?)\s*(?:m|米)[^。；;\n]{0,20}(?:鱼顶|卡|落|断)",
    ]
    value = _first_match(patterns, text)
    return float(value) if value else None


def _detect_well_type(text: str) -> str:
    candidates = ["水平井", "大斜度井", "定向井", "直井", "裸眼井", "套管井"]
    return "、".join(item for item in candidates if item in text)


def _detect_fish_type(text: str) -> str:
    candidates = ["钻杆", "钻铤", "油管", "套管", "接头", "工具", "钻具", "落物", "落鱼"]
    found = [item for item in candidates if item in text]
    if "钻具" in found and ("钻杆" in found or "钻铤" in found):
        found.remove("钻具")
    return "、".join(found)


def accident_parser_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured accident facts and missing fields from user text."""

    raw = (
        state.get("accident", {}).get("raw_description")
        or state.get("raw_description")
        or state.get("question")
        or ""
    ).strip()

    accident: Dict[str, Any] = {
        "raw_description": raw,
        "well_type": _detect_well_type(raw),
        "depth": _extract_depth(raw),
        "fish_type": _detect_fish_type(raw),
        "fish_description": _first_match(
            [
                r"(?:落鱼|落物|鱼顶|断落钻具)[为是:]?([^。；;\n]{2,80})",
                r"(?:断落|落井|掉落)([^。；;\n]{2,80})",
            ],
            raw,
        ),
        "mud_type": _first_match(
            [
                r"(?:泥浆|钻井液|井液)(?:密度)?[为是:]?\s*([0-9]+(?:\.[0-9]+)?\s*g/?cm(?:3|³)?)",
                r"((?:水基|油基|聚磺|盐水|清水|泡沫)[^。；;\n]{0,20}(?:泥浆|钻井液|井液))",
                r"(?:泥浆|钻井液|井液)[为是:]?([^。；;\n]{2,40})",
            ],
            raw,
        ),
        "additional_info": "",
    }
    llm_accident = _extract_with_llm(raw, state)
    if llm_accident:
        for key in [*FIELD_LABELS.keys(), "additional_info"]:
            value = llm_accident.get(key)
            if value not in (None, "", []):
                accident[key] = value
        if accident.get("depth"):
            try:
                accident["depth"] = float(accident["depth"])
            except (TypeError, ValueError):
                accident["depth"] = _extract_depth(raw)

    inclination = _first_match([r"(?:井斜|斜度|井斜角)[^0-9]{0,8}([0-9]+(?:\.[0-9]+)?\s*(?:°|度)?)"], raw)
    thread_type = _first_match([r"(?:扣型|接头扣型)[为是:]?([^。；;\n]{2,30})"], raw)
    if inclination and not accident.get("inclination"):
        accident["inclination"] = inclination
    if thread_type and not accident.get("thread_type"):
        accident["thread_type"] = thread_type

    missing = [label for key, label in FIELD_LABELS.items() if not accident.get(key)]
    accident["missing_fields"] = missing

    impact = []
    if "鱼顶深度/事故深度" in missing:
        impact.append("缺少鱼顶或事故深度会影响工具尺寸、管柱强度校核和作业窗口判断。")
    if "井斜角" in missing and "水平井" in accident.get("well_type", ""):
        impact.append("水平井缺少井斜轨迹信息时，摩阻、携砂和工具通过性需要现场复核。")
    if "扣型" in missing:
        impact.append("缺少扣型时，打捞连接和转换接头选择只能作为待确认项。")

    return {
        **state,
        "accident": accident,
        "parse_report": "\n".join(impact)
        or ("LLM 已辅助抽取当前描述中的关键事故信息，未识别信息保持为缺失项。" if llm_accident else "已抽取当前描述中的关键事故信息，未识别信息保持为缺失项。"),
    }


def _extract_with_llm(raw: str, state: Dict[str, Any]) -> Dict[str, Any] | None:
    if try_complete_json is None or not raw:
        return None
    prompt = f"""请从事故描述中抽取结构化字段，只返回 JSON 对象，不要输出解释。

字段：
- well_type: 井型，如水平井/大斜度井/直井等
- depth: 鱼顶深度或事故深度，数字米制；未知用 null
- fish_type: 落物/落鱼类型
- fish_description: 落物几何、状态、鱼顶状态等简要描述
- mud_type: 钻井液/井液类型或密度
- inclination: 井斜角
- thread_type: 扣型
- additional_info: 已采取措施、井下复杂情况、风险线索

事故描述：
{raw}
"""
    data = try_complete_json(
        prompt,
        system="你是钻井事故信息抽取助手。不得补造事实；未知字段必须留空或 null。",
        outputs_dir=state.get("outputs_dir") or "outputs",
        temperature=0.0,
        max_tokens=900,
    )
    return data if isinstance(data, dict) else None
