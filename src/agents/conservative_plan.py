"""Conservative staged planning agent."""

from __future__ import annotations

import os
from typing import Any, Dict

try:
    from src.wiki_loader import search_wiki_snippets
except Exception:
    search_wiki_snippets = None

try:
    from src.llm_client import try_complete_text
except Exception:
    try_complete_text = None


def conservative_plan_node(state: Dict[str, Any]) -> Dict[str, Any]:
    accident = state.get("accident", {})
    is_horizontal = "水平井" in accident.get("well_type", "")
    stages = [
        ("井况复核", "核实井控、井眼轨迹、鱼顶深度、落鱼尺寸、钻井液性能和已采取措施。"),
        ("循环洗井/冲砂", "在可循环条件下清洁井眼和鱼顶，水平井重点确认携砂能力。"),
        ("浸泡或解卡剂", "存在黏卡、压差卡等可能时，先采用低扰动解卡措施。"),
        ("震击解卡", "参数必须经强度校核和现场设计确认，不凭空给出精确值。"),
        ("打捞", "按落鱼形态、扣型、尺寸和鱼顶状态选择内捞或外捞工具。"),
        ("套铣/磨铣", "在打捞失败且风险可控时升级，持续监测扭矩、返砂和井况变化。"),
        ("侧钻或弃鱼", "多轮处置失败、风险升高或经济性不成立时提交技术论证。"),
    ]
    if is_horizontal:
        stages[1] = ("循环洗井/冲砂", "水平井先评估携砂、摩阻和工具通过性，再分段循环清洁井眼。")

    lines = ["## 保守方案", "目标：优先控制井控安全、井筒完整和事故扩大风险。", "", "### 阶梯式路径"]
    for idx, (title, body) in enumerate(stages, start=1):
        lines.append(f"{idx}. {title}：{body}")
    lines.extend(
        [
            "",
            "### 停止与升级条件",
            "- 任一阶段出现井控异常、循环异常、工具卡阻加重或关键参数缺失，应暂停并复核。",
            "- 前一阶段达到清洁、解卡或明确失败判据后，才进入下一阶段。",
            "",
            "### 关键标准摘录",
            *_standard_bullets(state, is_horizontal),
            "",
            "### 依据",
            "- [[解卡操作规程]]",
            "- [[水平井特殊工艺]]" if is_horizontal else "- 非水平井场景下按常规解卡打捞规程复核。",
            "- [[风险评估矩阵]]",
        ]
    )
    evidence = list(state.get("evidence", []))
    if search_wiki_snippets is not None:
        terms = ["6.1.4", "6.2震击法", "6.5套、磨铣法", "6.6浸泡法", "7打捞作业"]
        if is_horizontal:
            terms.extend(["水平井段", "6.5施工步骤", "7.4管柱冲砂"])
        for item in search_wiki_snippets(terms, state.get("wiki_dir") or "wiki", categories=("standards/",), limit=8):
            item["source_type"] = "standard"
            evidence.append(item)
    plan = _llm_refine_plan("\n".join(lines), {**state, "evidence": evidence})
    return {**state, "conservative_plan": plan, "evidence": evidence}


def _standard_bullets(state: Dict[str, Any], is_horizontal: bool) -> list[str]:
    if search_wiki_snippets is None:
        return ["- 标准摘录暂不可用，需人工复核 Wiki。"]
    terms = ["6.1.4", "6.2震击法", "6.5套、磨铣法", "7打捞作业"]
    if is_horizontal:
        terms.extend(["水平井段解卡顺序", "6.5施工步骤", "7.4.2", "7.5.1"])
    snippets = search_wiki_snippets(terms, state.get("wiki_dir") or "wiki", categories=("standards/",), limit=4)
    if not snippets:
        return ["- 未匹配到标准摘录，需人工复核 Wiki。"]
    bullets = []
    seen: set[str] = set()
    for item in snippets:
        page = item.get("source_page", "")
        page_no = item.get("page_no") or "待复核"
        summary = item.get("summary", "")
        if summary in seen:
            continue
        seen.add(summary)
        bullets.append(f"- {summary}（{page}，第 {page_no} 页）")
    return bullets


def _llm_refine_plan(draft: str, state: Dict[str, Any]) -> str:
    if try_complete_text is None or not _intermediate_refine_enabled():
        return draft
    prompt = f"""请基于事故信息和证据，把下面的保守处置方案改写为更清晰的阶梯式 Markdown。

硬性要求：
1. 保留“## 保守方案”标题。
2. 按“先复核、再清洁/冲砂、再解卡/打捞、最后升级”的顺序组织。
3. 明确停止条件和升级条件。
4. 不得编造现场参数；关键动作必须引用 Wiki 页面名或标注“工程推断”。

事故信息：
{state.get("accident", {})}

可用证据：
{_evidence_context(state.get("evidence", []))}

草稿：
{draft}
"""
    refined = try_complete_text(
        prompt,
        system="你是钻具落断事故处置专家，输出必须安全、可追溯、避免事故扩大。",
        outputs_dir=state.get("outputs_dir") or "outputs",
        temperature=0.2,
        max_tokens=1800,
    )
    if refined and "## 保守方案" in refined:
        return refined
    return draft


def _intermediate_refine_enabled() -> bool:
    return os.getenv("LLM_REFINE_INTERMEDIATE", "").strip().lower() in {"1", "true", "yes", "on"}


def _evidence_context(evidence: list[Dict[str, Any]], limit: int = 10) -> str:
    lines = []
    for item in evidence[:limit]:
        page = item.get("source_page") or ""
        summary = item.get("summary") or item.get("quote") or ""
        if page or summary:
            lines.append(f"- {page}：{summary}")
    return "\n".join(lines) or "暂无可用证据。"
