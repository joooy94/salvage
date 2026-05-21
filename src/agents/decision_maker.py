"""Final decision and output archiving agents."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

try:
    from src.llm_client import try_complete_text
except Exception:
    try_complete_text = None


def decision_maker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    accident = state.get("accident", {})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    missing = accident.get("missing_fields", [])
    evidence = state.get("evidence", [])
    wiki_pages = sorted({_normalize_page(item.get("source_page", "")) for item in evidence if item.get("source_page")})

    final = "\n".join(
        [
            "# 钻具落断事故处置方案",
            "",
            f"生成时间：{now}",
            f"方案置信度：{state.get('confidence_score', 0.5):.0%}",
            "",
            "## 事故概况",
            f"- 原始描述：{accident.get('raw_description', '') or '未提供'}",
            f"- 井型：{accident.get('well_type') or '待确认'}",
            f"- 深度/鱼顶：{accident.get('depth') or '待确认'}",
            f"- 落鱼类型：{accident.get('fish_type') or '待确认'}",
            f"- 钻井液/井液：{accident.get('mud_type') or '待确认'}",
            "",
            "## 关键不确定信息",
            "- " + ("、".join(missing) if missing else "当前输入未识别到关键缺失项，但现场参数仍需复核。"),
            "",
            "## 处置策略选择",
            "建议采用保守路径作为主线，在井况、工具尺寸和作业参数确认后，可吸收激进方案中的提速措施。",
            "",
            "## 分阶段处置方案",
            state.get("conservative_plan", "保守方案未生成。"),
            "",
            "## 快速恢复备选",
            state.get("aggressive_plan", "激进方案未生成。"),
            "",
            "## 判断节点",
            "- 井控、循环、返砂、扭矩、悬重、工具通过性任一异常即暂停升级。",
            "- 打捞失败后需复核鱼顶状态，再决定震击、套铣、磨铣或侧钻。",
            "",
            "## 应急预案",
            "- 井控异常：立即执行现场井控程序并暂停打捞。",
            "- 循环失效：停止下步强化措施，复核堵塞、沉砂和井眼清洁状况。",
            "- 工具卡阻：先卸载风险，再按解卡规程处理，避免事故扩大。",
            "",
            "## 合规审核",
            _strip_leading_heading(state.get("compliance_report", "合规审核未生成。"), "合规审核"),
            "",
            "## 关键引用摘录",
            *_evidence_lines(evidence),
            "",
            "## 参考依据",
            *(f"- [[{Path(page).stem}]]：{page}" for page in wiki_pages),
            "- 工程推断：所有无具体页码或条款的作业参数均需现场设计确认。",
            "",
            "## 注意事项与风险提示",
            "- 不得将缺失信息写成确定事实。",
            "- 不得凭空给出精确扭矩、拉力、震击参数。",
            "- 生成方案不得自动写入真实案例库。",
        ]
    )
    final = _llm_refine_final(final, state)

    return {**state, "final_plan": final, "wiki_pages_used": wiki_pages}


def _evidence_lines(evidence: list[Dict[str, Any]], limit: int = 10) -> list[str]:
    lines: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for item in sorted(evidence, key=_evidence_rank, reverse=True):
        source_page = _normalize_page(item.get("source_page", ""))
        summary = item.get("summary", "")
        if not source_page or not summary:
            continue
        quote = item.get("quote", "")
        if _is_low_value_evidence(summary, quote) and len(lines) >= 4:
            continue
        key = (source_page, summary, quote[:120])
        if key in seen:
            continue
        seen.add(key)
        page_no = item.get("page_no") or "待复核"
        if quote:
            quote = "；".join(line.strip() for line in quote.splitlines() if line.strip())[:180]
            lines.append(f"- {summary}（{source_page}，第 {page_no} 页）：{quote}")
        else:
            lines.append(f"- {summary}（{source_page}，第 {page_no} 页）")
        if len(lines) >= limit:
            break
    return lines or ["- 暂未形成可追溯摘录，需复核 Wiki 构建结果。"]


def _normalize_page(page: str) -> str:
    return page[5:] if page.startswith("wiki/") else page


def _evidence_rank(item: Dict[str, Any]) -> int:
    summary = str(item.get("summary", ""))
    quote = str(item.get("quote", ""))
    source_type = str(item.get("source_type", ""))
    score = 0
    if source_type == "case":
        score += 70
    if source_type == "standard":
        score += 30
    if item.get("clause"):
        score += 14
    if item.get("page_no"):
        score += 5
    if quote:
        score += 8
    if any(term in summary + quote for term in ["不应", "应", "宜", "施工步骤", "工艺要求", "解卡顺序", "可退工具"]):
        score += 10
    if any(term in summary + quote for term in ["本标准规定", "适用于", "相关页面", "合规审核覆盖"]):
        score -= 12
    return score


def _is_low_value_evidence(summary: str, quote: str) -> bool:
    text = summary + quote
    return any(term in text for term in ["本标准规定", "适用于", "相关页面", "合规审核覆盖"])


def _strip_leading_heading(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].strip() == f"## {heading}":
        return "\n".join(lines[1:]).lstrip()
    return markdown


def _llm_refine_final(draft: str, state: Dict[str, Any]) -> str:
    if try_complete_text is None:
        return draft
    prompt = f"""请对下面的最终处置方案做一次工程化审校和整合，输出完整 Markdown。

硬性要求：
1. 保留一级标题“# 钻具落断事故处置方案”。
2. 保留事故概况、关键不确定信息、分阶段处置、合规审核、关键引用摘录、参考依据、风险提示。
3. 不得新增未给出的现场参数，不得删除引用依据。
4. 如证据不足，必须降级为待确认或工程推断。
5. 生成方案不得写入真实案例库这一限制必须保留。

事故信息：
{state.get("accident", {})}

草稿：
{draft}
"""
    refined = try_complete_text(
        prompt,
        system="你是钻具落断事故处置方案总审，负责把专家输出整合为可执行、可追溯的最终方案。",
        outputs_dir=state.get("outputs_dir") or "outputs",
        temperature=0.15,
        max_tokens=2600,
    )
    if refined and "# 钻具落断事故处置方案" in refined:
        return refined
    return draft


def output_archiver_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Archive final plan to outputs and wiki/generated_plans without touching cases."""

    final_plan = state.get("final_plan", "")
    if not final_plan:
        return state

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"处置方案_{timestamp}.md"
    outputs_dir = Path(state.get("outputs_dir") or "outputs")
    wiki_generated_dir = Path(state.get("wiki_dir") or "wiki") / "generated_plans"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    wiki_generated_dir.mkdir(parents=True, exist_ok=True)

    output_path = outputs_dir / filename
    wiki_path = wiki_generated_dir / filename
    output_path.write_text(final_plan, encoding="utf-8")
    wiki_path.write_text(final_plan, encoding="utf-8")

    return {
        **state,
        "output_path": str(output_path),
        "generated_plan_path": str(wiki_path),
    }
