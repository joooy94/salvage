"""Compliance review agent."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from src.wiki_loader import search_wiki_snippets
except Exception:
    search_wiki_snippets = None


def compliance_checker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    accident = state.get("accident", {})
    missing: List[str] = accident.get("missing_fields", [])
    is_horizontal = "水平井" in accident.get("well_type", "")
    checks = [
        ("SY 5069-2017", "工具选型需与落鱼类型、尺寸、扣型和工具适用范围一致。"),
        ("SY/T 5587.12-2018", "解卡打捞应按井况复核、循环清洁、解卡、打捞和升级措施分阶段执行。"),
    ]
    if is_horizontal:
        checks.append(("SYT 6987-2024", "水平井处置需额外审核携砂、摩阻、井眼清洁和工具通过性。"))
    else:
        checks.append(("SYT 6987-2024", "当前未识别为水平井，仅作为适用性提示。"))

    findings = []
    if missing:
        findings.append(f"存在关键缺失信息：{'、'.join(missing)}。最终方案必须保持为待确认项。")
    if "参数" in state.get("aggressive_plan", ""):
        findings.append("强化处置涉及作业参数时已要求现场强度和井况设计确认。")
    if not state.get("evidence"):
        findings.append("未读取到 Wiki 证据，所有结论应降级为工程推断或待 Wiki 构建后复核。")

    report_lines = ["## 合规审核", "### 标准覆盖"]
    report_lines.extend(f"- {name}：{summary}" for name, summary in checks)
    report_lines.extend(["", "### 审核结论"])
    report_lines.extend(f"- {item}" for item in findings)
    if not findings:
        report_lines.append("- 未发现明显合规冲突，仍需现场参数复核。")

    confidence = 0.72
    if missing:
        confidence -= min(0.25, len(missing) * 0.03)
    if not state.get("similar_case_items"):
        confidence -= 0.12
    confidence = max(0.35, round(confidence, 2))

    evidence = list(state.get("evidence", []))
    standard_snippets = []
    if search_wiki_snippets is not None:
        terms = ["工具选型", "施工准备", "活动管柱", "震击", "套、磨铣", "打捞作业", "安全", "资料录取"]
        if is_horizontal:
            terms.extend(["水平井段", "可退工具", "冲砂"])
        standard_snippets = search_wiki_snippets(
            terms,
            state.get("wiki_dir") or "wiki",
            categories=("standards/",),
            limit=8,
        )
        for item in standard_snippets:
            item["source_type"] = "standard"
            evidence.append(item)
    for page, pdf in [
        ("wiki/standards/打捞工具目录.md", "SY 5069-2017石油天然气工业钻井和采油设备 管柱类落物打捞工具.pdf"),
        ("wiki/standards/解卡操作规程.md", "SY_T 5587.12-2018常规修井作业规程 第12部分：解卡打捞.pdf"),
    ]:
        evidence.append(
            {
                "source_type": "standard",
                "source_page": page,
                "source_pdf": pdf,
                "page_no": None,
                "clause": None,
                "quote": "",
                "summary": "合规审核覆盖的标准页面，具体条款见标准摘录。",
            }
        )
    if is_horizontal:
        evidence.append(
            {
                "source_type": "standard",
                "source_page": "wiki/standards/水平井特殊工艺.md",
                "source_pdf": "SYT 6987-2024 水平井解卡打捞及冲砂方法.pdf",
                "page_no": None,
                "clause": None,
                "quote": "",
                "summary": "水平井特殊工艺合规审核。",
            }
        )

    return {
        **state,
        "compliance_report": "\n".join(report_lines),
        "confidence_score": confidence,
        "evidence": evidence,
    }
