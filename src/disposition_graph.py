"""Build a session-scoped disposition knowledge graph.

This graph is intentionally different from the Wiki page-link graph. It uses
engineering entities such as accident features, risks, procedures, tools and
evidence so the graph can explain why a plan recommends a certain path.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


Graph = Dict[str, List[Dict[str, Any]]]


RISK_RULES = [
    ("risk_sand", "沉砂/砂埋风险", ["返砂", "沉砂", "砂埋", "砂桥"], "鱼顶附近沉砂或返砂异常会影响工具下入和打捞成功率。"),
    ("risk_circulation", "循环通道受限", ["泵压", "循环压力", "憋泵", "不通", "压波动", "压力波动"], "泵压升高或波动提示环空/鱼顶附近通道可能受限。"),
    ("risk_high_angle", "大井斜携砂困难", ["水平井", "井斜", "78", "大斜度"], "水平井或大井斜段携砂效率下降，清洁井眼应前置。"),
    ("risk_stuck", "二次卡钻/卡阻加重", ["卡钻", "未能活动", "上提未能", "遇阻", "卡阻"], "落鱼和井眼复杂叠加时，强行下工具可能扩大事故。"),
    ("risk_uncertain_top", "鱼顶与扣型不确定", ["鱼顶不清", "扣型不", "扣型暂不明确", "断口", "鱼顶形态"], "鱼顶形态或扣型未确认会直接影响内捞/外捞工具选择。"),
    ("risk_well_control", "井控与井筒完整风险", ["井控", "溢流", "漏失", "井壁", "坍塌"], "井控或井壁异常时，处置方案需先降风险再作业。"),
]

PROCEDURE_RULES = [
    ("proc_review", "井况复核", ["复核", "核实", "确认井况", "井况"], "先确认井控、井眼轨迹、鱼顶、落鱼尺寸和已采取措施。"),
    ("proc_clean", "循环洗井/冲砂", ["循环洗井", "洗井", "冲砂", "清洁井眼", "恢复循环", "稳定循环"], "用于降低沉砂、返砂和通道受限风险，是水平井复杂井况下的关键前置步骤。"),
    ("proc_tag_top", "探鱼顶/鱼顶确认", ["探鱼顶", "鱼顶确认", "鱼顶形态", "沉砂高度"], "确认鱼顶位置、形态和覆盖情况后再选择打捞工具。"),
    ("proc_soak", "解卡剂浸泡", ["解卡剂", "浸泡", "泡解卡"], "适用于低扰动解卡或疑似黏卡/压差卡情形。"),
    ("proc_jarring", "震击解卡", ["震击", "震击器"], "循环稳定且强度校核后可用于解卡或辅助打捞。"),
    ("proc_fishing", "内捞/外捞", ["内捞", "外捞", "打捞", "捞矛", "打捞筒", "公锥", "母锥"], "依据落鱼尺寸、扣型、鱼顶形态选择内捞或外捞工具。"),
    ("proc_milling", "套铣/磨铣", ["套铣", "磨铣", "磨鞋"], "在直接打捞失败或鱼顶复杂时升级，需监控扭矩、返砂和进尺。"),
    ("proc_sidetrack", "侧钻/弃鱼论证", ["侧钻", "弃鱼"], "多轮处置失败或经济/安全风险不成立时作为最终备选。"),
]

TOOL_RULES = [
    ("tool_spear", "打捞矛", ["打捞矛", "捞矛", "内捞矛"]),
    ("tool_overshot", "卡瓦打捞筒", ["打捞筒", "卡瓦打捞筒", "外捞筒"]),
    ("tool_tap", "打捞公锥", ["公锥"]),
    ("tool_box_tap", "打捞母锥", ["母锥"]),
    ("tool_jar", "震击器", ["震击器"]),
    ("tool_washover", "套铣筒", ["套铣筒", "套铣"]),
    ("tool_mill", "磨鞋", ["磨鞋", "磨铣"]),
    ("tool_safety", "安全接头", ["安全接头"]),
    ("tool_reverse", "反循环打捞篮", ["反循环打捞篮"]),
]


def build_disposition_graph(session: Dict[str, Any]) -> Graph:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    def add_node(node_id: str, label: str, node_type: str, level: int, summary: str = "", source_page: str = "") -> None:
        if node_id in nodes:
            return
        nodes[node_id] = {
            "id": node_id,
            "label": label,
            "type": node_type,
            "level": level,
            "summary": summary,
            "source_page": source_page,
        }

    def add_edge(source: str, target: str, label: str, edge_type: str) -> None:
        if source == target or source not in nodes or target not in nodes:
            return
        edge = {"source": source, "target": target, "label": label, "type": edge_type}
        if edge not in edges:
            edges.append(edge)

    accident = session.get("accident") if isinstance(session.get("accident"), dict) else {}
    description = str(session.get("description") or accident.get("raw_description") or "当前事故")
    text = _session_text(session)
    add_node("accident_current", "当前事故", "accident", 0, description[:180])

    for node_id, label, value in _accident_features(accident):
        add_node(node_id, label, "feature", 1, str(value))
        add_edge("accident_current", node_id, "具备特征", "has_feature")

    missing_fields = accident.get("missing_fields") if isinstance(accident.get("missing_fields"), list) else []
    if missing_fields:
        add_node("risk_missing_info", "关键信息缺失", "risk", 2, "缺失：" + "、".join(map(str, missing_fields)))
        add_edge("accident_current", "risk_missing_info", "带来不确定性", "has_risk")

    risk_ids = []
    if missing_fields:
        risk_ids.append("risk_missing_info")
    for node_id, label, keywords, summary in RISK_RULES:
        if _contains_any(text, keywords):
            add_node(node_id, label, "risk", 2, summary)
            risk_ids.append(node_id)
            add_edge("accident_current", node_id, "触发风险", "has_risk")

    procedure_ids = []
    for node_id, label, keywords, summary in PROCEDURE_RULES:
        if _contains_any(text, keywords):
            add_node(node_id, label, "procedure", 3, summary)
            procedure_ids.append(node_id)

    if not procedure_ids and session.get("final_plan"):
        for node_id in ["proc_review", "proc_clean", "proc_fishing"]:
            rule = next(item for item in PROCEDURE_RULES if item[0] == node_id)
            add_node(rule[0], rule[1], "procedure", 3, rule[3])
            procedure_ids.append(node_id)

    _connect_risks_to_procedures(risk_ids, procedure_ids, add_edge)
    _connect_procedure_chain(procedure_ids, add_edge)

    for node_id, label, keywords in TOOL_RULES:
        if _contains_any(text, keywords):
            add_node(node_id, label, "tool", 4, "方案或案例中提到的处置工具。")
            if node_id in {"tool_spear", "tool_overshot", "tool_tap", "tool_box_tap"}:
                add_edge("proc_fishing", node_id, "采用工具", "uses_tool")
            elif node_id == "tool_jar":
                add_edge("proc_jarring", node_id, "采用工具", "uses_tool")
            elif node_id in {"tool_washover", "tool_mill"}:
                add_edge("proc_milling", node_id, "采用工具", "uses_tool")
            else:
                add_edge("proc_review", node_id, "配套工具", "uses_tool")

    for index, item in enumerate(_evidence_items(session)):
        source_type = str(item.get("source_type") or "evidence")
        page = str(item.get("source_page") or "")
        label = _evidence_label(item, index)
        node_id = f"evidence_{index}"
        add_node(node_id, label, source_type if source_type in {"standard", "case", "synthesis"} else "evidence", 5, str(item.get("summary") or item.get("quote") or ""), page)
        for target in _evidence_targets(source_type, procedure_ids):
            add_edge(target, node_id, "依据", "supported_by")

    final_plan = str(session.get("final_plan") or "")
    if final_plan:
        add_node("decision_final", "最终处置方案", "decision", 6, _first_nonempty_line(final_plan))
        if procedure_ids:
            add_edge(procedure_ids[-1], "decision_final", "汇总形成", "leads_to")
        else:
            add_edge("accident_current", "decision_final", "生成方案", "leads_to")

    return {"nodes": list(nodes.values()), "edges": edges}


def _accident_features(accident: Dict[str, Any]) -> Iterable[tuple[str, str, Any]]:
    fields = [
        ("well_type", "井型", "feature_well"),
        ("depth", "事故深度", "feature_depth"),
        ("fish_top_depth", "鱼顶深度", "feature_fish_top"),
        ("fish_type", "落鱼类型", "feature_fish"),
        ("fish_description", "落鱼描述", "feature_fish_desc"),
        ("mud_type", "钻井液", "feature_mud"),
        ("mud_density", "井液密度", "feature_mud_density"),
        ("thread_type", "扣型", "feature_thread"),
        ("connection_type", "扣型", "feature_connection"),
        ("inclination", "井斜角", "feature_inclination"),
    ]
    seen = set()
    for key, label, node_id in fields:
        value = accident.get(key)
        if value in (None, "", []):
            continue
        if label in seen and label == "扣型":
            continue
        seen.add(label)
        yield node_id, f"{label}: {value}", value


def _session_text(session: Dict[str, Any]) -> str:
    parts = [
        session.get("description", ""),
        session.get("parse_report", ""),
        session.get("similar_cases", ""),
        session.get("aggressive_plan", ""),
        session.get("conservative_plan", ""),
        session.get("compliance_report", ""),
        session.get("final_plan", ""),
        " ".join(str(item.get("content", "")) for item in session.get("messages", []) if isinstance(item, dict)),
    ]
    accident = session.get("accident")
    if isinstance(accident, dict):
        parts.append(" ".join(str(value) for value in accident.values()))
    return "\n".join(str(part) for part in parts if part)


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword and keyword in text for keyword in keywords)


def _connect_risks_to_procedures(risk_ids: List[str], procedure_ids: List[str], add_edge) -> None:
    if "risk_missing_info" in risk_ids:
        for proc in ["proc_review", "proc_tag_top"]:
            if proc in procedure_ids:
                add_edge("risk_missing_info", proc, "前置确认", "mitigated_by")
    if "risk_uncertain_top" in risk_ids:
        for proc in ["proc_review", "proc_tag_top"]:
            if proc in procedure_ids:
                add_edge("risk_uncertain_top", proc, "前置确认", "mitigated_by")
    if "risk_sand" in risk_ids or "risk_circulation" in risk_ids or "risk_high_angle" in risk_ids:
        for proc in ["proc_clean", "proc_tag_top"]:
            if proc in procedure_ids:
                for risk in [risk for risk in risk_ids if risk in {"risk_sand", "risk_circulation", "risk_high_angle"}]:
                    add_edge(risk, proc, "优先控制", "mitigated_by")
    if "risk_stuck" in risk_ids:
        for proc in ["proc_soak", "proc_jarring", "proc_fishing"]:
            if proc in procedure_ids:
                add_edge("risk_stuck", proc, "阶梯处置", "mitigated_by")
    if "risk_well_control" in risk_ids and "proc_review" in procedure_ids:
        add_edge("risk_well_control", "proc_review", "先复核", "mitigated_by")


def _connect_procedure_chain(procedure_ids: List[str], add_edge) -> None:
    order = [item[0] for item in PROCEDURE_RULES]
    ordered = [node_id for node_id in order if node_id in procedure_ids]
    for source, target in zip(ordered, ordered[1:]):
        add_edge(source, target, "满足条件后升级", "next_step")


def _evidence_items(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence = session.get("evidence")
    if isinstance(evidence, list) and evidence:
        return [item for item in evidence if isinstance(item, dict)][:12]
    pages = session.get("wiki_pages_used")
    if isinstance(pages, list):
        return [{"source_type": _infer_source_type(str(page)), "source_page": str(page), "summary": str(page)} for page in pages[:12]]
    return []


def _evidence_label(item: Dict[str, Any], index: int) -> str:
    page = str(item.get("source_page") or "")
    if page:
        return page.split("/")[-1].replace(".md", "")
    source_pdf = str(item.get("source_pdf") or "")
    return source_pdf.replace(".pdf", "") or f"依据 {index + 1}"


def _infer_source_type(page: str) -> str:
    if page.startswith("standards/") or "/standards/" in page:
        return "standard"
    if page.startswith("cases/") or "/cases/" in page:
        return "case"
    if page.startswith("synthesis/") or "/synthesis/" in page:
        return "synthesis"
    return "evidence"


def _evidence_targets(source_type: str, procedure_ids: List[str]) -> List[str]:
    if source_type == "standard":
        return [node_id for node_id in ["proc_review", "proc_clean", "proc_fishing", "proc_jarring", "proc_milling"] if node_id in procedure_ids] or procedure_ids[:1]
    if source_type == "case":
        return ["accident_current"]
    if source_type == "synthesis":
        return procedure_ids[:3]
    return procedure_ids[:1] or ["accident_current"]


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        clean = line.strip().strip("#").strip()
        if clean:
            return clean[:180]
    return "已生成最终处置方案。"
