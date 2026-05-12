"""Aggressive but compliant planning agent."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from src.wiki_loader import search_wiki_snippets
except Exception:
    search_wiki_snippets = None


def aggressive_plan_node(state: Dict[str, Any]) -> Dict[str, Any]:
    accident = state.get("accident", {})
    missing: List[str] = accident.get("missing_fields", [])
    is_horizontal = "水平井" in accident.get("well_type", "")

    step_text = [
        "快速复核井控、循环通道、鱼顶深度和落鱼几何尺寸；缺失参数不得用经验值替代。",
        "在确认井筒稳定和可循环后，优先恢复循环、洗井或冲砂，清理鱼顶和沉砂。",
        "根据鱼顶形态选择外捞、内捞或母锥/公锥类工具，扣型和尺寸需现场复核。",
        "若常规打捞无效，转入震击、套铣或磨铣等强化路径；扭矩、拉力、震击参数需结合钻具强度、井况和现场设计确认。",
    ]
    if is_horizontal:
        step_text.insert(2, "水平井需额外校核工具通过性、摩阻、携砂能力和井眼清洁效果。")
    steps = [f"{idx}. {text}" for idx, text in enumerate(step_text, start=1)]

    citations = ["引用：[[打捞工具目录]]、[[解卡操作规程]]"]
    if is_horizontal:
        citations.append("水平井补充引用：[[水平井特殊工艺]]")
    citations.append("案例参考：")
    if state.get("similar_cases"):
        citations.extend(state["similar_cases"].splitlines())
    else:
        citations.append("- 暂无可用案例页")
    evidence = list(state.get("evidence", []))
    if search_wiki_snippets is not None:
        terms = ["打捞工具", "打捞矛", "打捞筒", "公锥", "母锥", "可退工具", "活动管柱法", "震击法", "套、磨铣法"]
        if is_horizontal:
            terms.extend(["井下液压增力法", "冲砂", "水平井段"])
        for item in search_wiki_snippets(terms, state.get("wiki_dir") or "wiki", categories=("standards/",), limit=6):
            item["source_type"] = "standard"
            evidence.append(item)
    plan = "\n".join(
        [
            "## 激进方案",
            "目标：在合规边界内尽快恢复作业，缩短停工时间。",
            "",
            "### 行动步骤",
            *steps,
            "",
            "### 转入条件",
            "- 出现井控风险、循环失效、工具遇阻异常或关键参数无法确认时，立即转入保守路径。",
            "- " + ("缺失信息：" + "、".join(missing) if missing else "当前描述未识别到关键缺失项。"),
            "",
            "### 依据",
            *[item for item in citations if item],
        ]
    )
    return {**state, "aggressive_plan": plan, "evidence": evidence}
