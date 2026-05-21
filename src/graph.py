"""LangGraph orchestration for the online accident disposition pipeline."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Literal, TypedDict

from .agents import (
    accident_parser_node,
    aggressive_plan_node,
    case_matcher_node,
    compliance_checker_node,
    conservative_plan_node,
    decision_maker_node,
    output_archiver_node,
)
from .agents.accident_parser import FIELD_LABELS

try:
    from .llm_client import load_llm_config, try_complete_json, try_complete_text
except Exception:
    load_llm_config = None
    try_complete_json = None
    try_complete_text = None


try:
    from .state import AgentState as BaseAgentState
    from .state import ConversationState as BaseConversationState
except Exception:
    class BaseAgentState(TypedDict, total=False):
        accident: Dict[str, Any]
        evidence: list[Dict[str, Any]]
        similar_cases: str
        aggressive_plan: str
        conservative_plan: str
        compliance_report: str
        final_plan: str
        debate_rounds: list[Dict[str, Any]]
        wiki_pages_used: list[str]
        confidence_score: float
        output_path: str

    class BaseConversationState(TypedDict, total=False):
        user_input: str
        input_intent: str
        route_reason: str
        accident: Dict[str, Any]
        evidence: list[Dict[str, Any]]
        current_plan: str
        final_plan: str
        answer: str
        debate_rounds: list[Dict[str, Any]]
        plan_updated: bool
        mode: str


class AgentState(BaseAgentState, total=False):
    wiki_dir: str
    outputs_dir: str
    question: str
    raw_description: str


class ConversationState(BaseConversationState, total=False):
    wiki_dir: str
    outputs_dir: str


PIPELINE: tuple[Callable[[Dict[str, Any]], Dict[str, Any]], ...] = (
    accident_parser_node,
    case_matcher_node,
    aggressive_plan_node,
    conservative_plan_node,
    compliance_checker_node,
    decision_maker_node,
    output_archiver_node,
)


class SequentialGraph:
    """Small fallback with LangGraph-like invoke semantics."""

    def __init__(self, nodes: Iterable[Callable[[Dict[str, Any]], Dict[str, Any]]]):
        self.nodes = tuple(nodes)

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        current = dict(state)
        for node in self.nodes:
            current = node(current)
        return current


def build_graph() -> Any:
    """Build the LangGraph state machine, falling back to a serial runner."""

    try:
        from langgraph.graph import END, START, StateGraph
    except Exception:
        return SequentialGraph(PIPELINE)

    graph = StateGraph(AgentState)
    graph.add_node("accident_parser", accident_parser_node)
    graph.add_node("case_matcher", case_matcher_node)
    graph.add_node("aggressive_plan", _planning_delta(aggressive_plan_node, "aggressive_plan"))
    graph.add_node("conservative_plan", _planning_delta(conservative_plan_node, "conservative_plan"))
    graph.add_node("compliance_checker", _delta_node(compliance_checker_node, ("compliance_report", "confidence_score")))
    graph.add_node("decision_maker", _delta_node(decision_maker_node, ("final_plan", "wiki_pages_used")))
    graph.add_node("output_archiver", _delta_node(output_archiver_node, ("output_path", "generated_plan_path")))

    graph.add_edge(START, "accident_parser")
    graph.add_edge("accident_parser", "case_matcher")
    graph.add_edge("case_matcher", "aggressive_plan")
    graph.add_edge("case_matcher", "conservative_plan")
    graph.add_edge("conservative_plan", "compliance_checker")
    graph.add_edge("aggressive_plan", "compliance_checker")
    graph.add_edge("compliance_checker", "decision_maker")
    graph.add_edge("decision_maker", "output_archiver")
    graph.add_edge("output_archiver", END)
    return graph.compile()


def build_conversation_graph() -> Any:
    """Build the multi-turn conversation graph for follow-ups and revisions."""

    try:
        from langgraph.graph import END, START, StateGraph
    except Exception:
        return ConversationGraphFallback()

    graph = StateGraph(ConversationState)
    graph.add_node("router", conversation_router_node)
    graph.add_node("explain", explain_node)
    graph.add_node("state_update", state_update_node)
    graph.add_node("case_refresh", case_matcher_node)
    graph.add_node("debate", debate_node)
    graph.add_node("compliance", compliance_checker_node)
    graph.add_node("revision", revision_decision_node)
    graph.add_node("archive_revision", archive_revision_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _route_from_mode,
        {
            "solve": "state_update",
            "explain": "explain",
            "finalize": "finalize",
        },
    )
    graph.add_edge("state_update", "case_refresh")
    graph.add_edge("case_refresh", "debate")
    graph.add_edge("debate", "compliance")
    graph.add_edge("compliance", "revision")
    graph.add_edge("revision", "archive_revision")
    graph.add_edge("explain", END)
    graph.add_edge("archive_revision", END)
    graph.add_edge("finalize", END)
    return graph.compile()


class ConversationGraphFallback:
    """Fallback runner for environments without LangGraph."""

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        current = conversation_router_node(state)
        route = _route_from_mode(current)
        if route == "explain":
            return explain_node(current)
        if route == "finalize":
            return finalize_node(current)
        current = state_update_node(current)
        current = case_matcher_node(current)
        current = debate_node(current)
        current = compliance_checker_node(current)
        current = revision_decision_node(current)
        return archive_revision_node(current)


def conversation_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Classify the user's turn against the current accident session."""

    text = str(state.get("user_input") or state.get("question") or "").strip()
    has_plan = bool(str(state.get("current_plan") or state.get("final_plan") or "").strip())
    requested_mode = str(state.get("requested_mode") or "").strip()
    if not has_plan:
        return {**state, "mode": "solve", "input_intent": "solve", "route_reason": "当前会话尚无方案，进入主流程辩论并生成方案。"}
    if requested_mode in {"explain", "solve"}:
        reason = "用户在前端明确选择“解释当前方案”。" if requested_mode == "explain" else "用户在前端明确选择“重新评估方案”。"
        return {**state, "mode": requested_mode, "input_intent": requested_mode, "route_reason": reason}

    mode, reason = _classify_conversation_mode(text, state)
    return {**state, "mode": mode, "input_intent": mode, "route_reason": reason}


def _classify_conversation_mode(text: str, state: Dict[str, Any]) -> tuple[str, str]:
    has_plan = bool(str(state.get("current_plan") or state.get("final_plan") or "").strip())
    if not has_plan:
        return "solve", "当前会话尚无方案，进入主流程辩论并生成方案。"
    if any(term in text for term in ["定稿", "正式版", "导出", "最终版", "归档当前"]):
        return "finalize", "用户要求形成或导出正式结果。"
    if _looks_like_solve_request(text):
        return "solve", "本轮输入要求补充事实、重新评估或生成修订方案，进入主流程辩论。"
    if _looks_like_explanation_question(text):
        return "explain", "本轮输入是对当前方案的追问解释，不生成新方案版本。"
    return "explain", "默认按追问解释处理；如需修订方案，请输入“重新评估/重新生成/修订方案”。"


def _looks_like_solve_request(text: str) -> bool:
    solve_terms = ["重新评估", "重新生成", "重算", "修订方案", "修改方案", "更新方案", "调整方案", "生成方案", "给出处置方案"]
    if any(term in text for term in solve_terms):
        return True
    return _looks_like_fact_update(text)


def _looks_like_fact_update(text: str) -> bool:
    fact_terms = [
        "补充",
        "新增",
        "井斜",
        "斜度",
        "扣型",
        "鱼顶",
        "沉砂",
        "返砂",
        "密度",
        "泵压",
        "扭矩",
        "悬重",
        "循环",
        "震击",
        "套铣",
        "已尝试",
        "现场",
        "长度",
        "尺寸",
    ]
    return any(term in text for term in fact_terms) and bool(re.search(r"\d|未能|不畅|异常|稳定|不稳定|明显|已经|已", text))


def _looks_like_explanation_question(text: str) -> bool:
    if any(term in text for term in ["请重新评估", "修改", "修订", "调整方案", "重算", "改成"]):
        return False
    return text.startswith("为什么") or "依据是什么" in text or "原因" in text or "请解释" in text


def _route_from_mode(state: Dict[str, Any]) -> Literal["solve", "explain", "finalize"]:
    mode = str(state.get("mode") or state.get("input_intent") or "explain")
    if mode in {"solve", "explain", "finalize"}:
        return mode  # type: ignore[return-value]
    return "explain"


def explain_node(state: Dict[str, Any]) -> Dict[str, Any]:
    question = str(state.get("user_input") or "")
    prompt = f"""请基于同一事故会话回答用户追问，不要重新生成完整处置方案。

要求：
1. 只回答追问本身，必要时引用已有方案、标准页、案例页或标注工程推断。
2. 不得编造标准条款、页码、扭矩、拉力、震击参数。
3. 如追问需要新增现场信息，明确说明需要补充什么。

事故信息：
{json.dumps(state.get("accident", {}), ensure_ascii=False)}

当前最终方案：
{str(state.get("current_plan") or state.get("final_plan") or "")[:7000]}

合规审核：
{str(state.get("compliance_report", ""))[:2500]}

用户追问：
{question}
"""
    answer = _try_text(
        prompt,
        system="你是钻具落断事故处置方案问答助手，只基于当前会话上下文作答。",
        state=state,
        max_tokens=1600,
    ) or _fallback_question_answer(question, state)
    return {**state, "answer": answer, "mode": "explain", "input_intent": "explain", "plan_updated": False}


def state_update_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge the user turn into the current accident state before solving."""

    parsed = accident_parser_node(
        {
            **state,
            "accident": {"raw_description": str(state.get("user_input") or "")},
            "raw_description": str(state.get("user_input") or ""),
        }
    )
    old_accident = dict(state.get("accident", {}))
    new_accident = dict(parsed.get("accident", {}))
    merged = {**old_accident}
    for key, value in new_accident.items():
        if key in {"missing_fields"}:
            continue
        if value not in (None, "", []):
            if key == "raw_description" and old_accident.get("raw_description"):
                merged[key] = f"{old_accident.get('raw_description')}\n\n补充信息：{value}"
            else:
                merged[key] = value
    merged["missing_fields"] = [label for key, label in FIELD_LABELS.items() if not merged.get(key)]

    is_initial = not old_accident or not state.get("current_plan")
    title = "事故信息提取" if is_initial else "事故状态更新"
    update_report = "\n".join(
        [
            f"## {title}",
            f"- 处理模式：solve，{state.get('route_reason') or '进入主流程辩论并生成方案。'}",
            f"- {'已识别字段' if is_initial else '已更新字段'}：{_changed_fields({}, merged) if is_initial else (_changed_fields(old_accident, merged) or '未识别到可直接写入的结构化字段，作为补充说明保留。')}",
            f"- 仍缺失：{'、'.join(merged.get('missing_fields') or []) or '暂无关键缺失项。'}",
        ]
    )
    return {
        **state,
        "accident": merged,
        "parse_report": update_report,
        "mode": "solve",
    }


def debate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the main multi-round debate between the aggressive and conservative agents."""

    current = {
        **state,
        "evidence": list(state.get("evidence", [])),
    }
    aggressive_state = aggressive_plan_node(current)
    current = {**current, **aggressive_state}
    conservative_state = conservative_plan_node(current)
    current = {**current, **conservative_state}

    debate_rounds = _make_debate_rounds(current)
    debate_markdown = _debate_markdown(debate_rounds)
    return {
        **current,
        "debate_rounds": debate_rounds,
        "answer": debate_markdown,
        "mode": "solve",
        "plan_updated": True,
    }


def revision_decision_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Create the final plan from the main debate outcome."""

    base = decision_maker_node(state)
    debate = _debate_markdown(base.get("debate_rounds", []))
    final = base.get("final_plan", "")
    revised = _try_text(
        f"""请基于事故信息、本轮用户输入和双方 Agent 辩论，生成完整“钻具落断事故处置方案”Markdown。

要求：
1. 必须以“# 钻具落断事故处置方案”开头。
2. 必须包含“本轮新增/确认信息”“Agent 辩论裁决”“分阶段处置方案”“关键判断节点”“工具清单”“风险提示”“参考依据”。
3. 如果当前已有旧方案，保留仍然成立的依据和风险提示，并说明本轮修订点。
4. 辩论过程只能作为依据，最终输出必须是可执行方案，不要只输出辩论摘要。
5. 不得编造具体工程参数或标准条款；缺失参数必须写“需现场设计确认”。

本轮输入：
{state.get("user_input", "")}

事故信息：
{json.dumps(base.get("accident", {}), ensure_ascii=False)}

双方辩论：
{debate}

合规审核：
{base.get("compliance_report", "")}

当前旧方案：
{str(state.get("current_plan") or "")[:4000]}

方案草稿：
{final}
""",
        system="你是钻井作业总监，负责把多轮辩论裁决为可执行、可追溯的修订方案。",
        state=base,
        max_tokens=3000,
    )
    if revised and "# 钻具落断事故处置方案" in revised:
        final = revised
    elif debate:
        final = "\n".join([final, "", "## 本轮 Agent 辩论与修订依据", debate])

    answer = "\n".join(
        [
            "## 已完成主流程辩论并生成方案",
            "",
            f"- 处理模式：solve",
            f"- 路由原因：{base.get('route_reason') or '基于当前会话触发多 Agent 复核。'}",
            "- 激进处置 Agent 与保守安全 Agent 已完成主流程辩论，合规审核后由决策 Agent 生成最终方案。",
            "",
            "### 本轮辩论摘要",
            debate,
        ]
    )
    return {
        **base,
        "final_plan": final,
        "current_plan": final,
        "answer": answer,
        "plan_updated": True,
    }


def archive_revision_node(state: Dict[str, Any]) -> Dict[str, Any]:
    if not state.get("final_plan"):
        return state
    return output_archiver_node(state)


def finalize_node(state: Dict[str, Any]) -> Dict[str, Any]:
    answer = "\n".join(
        [
            "## 当前方案可作为会话定稿",
            "",
            "当前会话已有最终方案。若需要正式导出，可使用页面右上角导出按钮。",
            "",
            f"- 定稿时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 当前置信度：{float(state.get('confidence_score') or 0):.0%}",
            f"- 仍缺失信息：{'、'.join(state.get('accident', {}).get('missing_fields', [])) or '暂无关键缺失项。'}",
        ]
    )
    return {**state, "answer": answer, "mode": "finalize", "plan_updated": False}


def converse_accident(
    user_input: str,
    session_state: Dict[str, Any] | None = None,
    *,
    wiki_dir: str = "wiki",
    outputs_dir: str = "outputs",
    mode: str | None = None,
) -> Dict[str, Any]:
    """Run one conversational turn against an existing accident session."""

    session_state = session_state or {}
    initial: Dict[str, Any] = {
        **session_state,
        "user_input": user_input,
        "current_plan": session_state.get("final_plan") or session_state.get("current_plan") or "",
        "wiki_dir": wiki_dir,
        "outputs_dir": outputs_dir,
        "requested_mode": mode,
        "evidence": list(session_state.get("evidence", [])),
        **_llm_state(outputs_dir),
    }
    return build_conversation_graph().invoke(initial)


def _make_debate_rounds(state: Dict[str, Any]) -> list[Dict[str, Any]]:
    prompt = f"""请模拟两个钻具落断事故处置 Agent 围绕本轮输入进行两轮短辩论，输出 JSON。

Agent：
1. aggressive：激进处置 Agent，目标是尽快恢复作业，但必须合规。
2. conservative：保守安全 Agent，目标是井控安全和防止事故扩大。
3. decision：裁决 Agent，综合双方意见给出修订方向。

要求：
- 每条 content 不超过 220 字。
- 必须围绕本轮输入，不要重新复述完整方案。
- 无依据参数必须写“需现场设计确认”。

返回格式：
{{"rounds":[{{"agent":"aggressive","title":"...","content":"..."}}, ...]}}

事故信息：
{json.dumps(state.get("accident", {}), ensure_ascii=False)}

本轮输入：
{state.get("user_input", "")}

激进方案：
{str(state.get("aggressive_plan", ""))[:2500]}

保守方案：
{str(state.get("conservative_plan", ""))[:2500]}

当前方案：
{str(state.get("current_plan") or state.get("final_plan") or "")[:3500]}
"""
    if try_complete_json is not None:
        data = try_complete_json(
            prompt,
            system="你是多 Agent 辩论记录员，只输出 JSON。",
            outputs_dir=state.get("outputs_dir") or "outputs",
            temperature=0.15,
            max_tokens=1200,
        )
        rounds = data.get("rounds") if isinstance(data, dict) else None
        if isinstance(rounds, list) and rounds:
            return [
                {
                    "agent": str(item.get("agent") or "agent"),
                    "title": str(item.get("title") or _agent_title(str(item.get("agent") or "agent"))),
                    "content": str(item.get("content") or ""),
                }
                for item in rounds
                if isinstance(item, dict) and item.get("content")
            ][:6]

    user_input = str(state.get("user_input") or "")
    return [
        {
            "agent": "aggressive",
            "title": "激进处置 Agent 第一轮",
            "content": f"本轮输入提示需要复核是否可以提高处置效率。若井控、循环和工具通过性均确认，可保留快速打捞或强化处置作为备选；涉及拉力、扭矩、震击等参数仍需现场设计确认。用户输入：{user_input[:120]}",
        },
        {
            "agent": "conservative",
            "title": "保守安全 Agent 第一轮",
            "content": "当前方案仍应先关闭沉砂、循环异常、鱼顶状态和扣型等不确定性。若这些条件未确认，直接升级打捞可能增加卡阻、鱼顶破坏或井控风险。",
        },
        {
            "agent": "aggressive",
            "title": "激进处置 Agent 第二轮",
            "content": "同意先设定停止条件，但建议把可执行窗口写清：一旦循环稳定、鱼顶清洁、工具尺寸和扣型确认，可立即转入匹配工具打捞，避免无效等待。",
        },
        {
            "agent": "conservative",
            "title": "保守安全 Agent 第二轮",
            "content": "转入打捞前必须保留复核节点：返砂、泵压、悬重、扭矩或工具遇阻任一异常，都应暂停并复核井眼清洁和鱼顶状态。",
        },
        {
            "agent": "decision",
            "title": "裁决 Agent",
            "content": "采纳保守路径作为主线，同时吸收激进方案的条件化提速建议：满足循环稳定、鱼顶清洁、扣型尺寸确认后，允许进入直接打捞窗口。",
        },
    ]


def _debate_markdown(rounds: list[Dict[str, Any]]) -> str:
    if not rounds:
        return "暂无辩论记录。"
    lines = []
    for index, item in enumerate(rounds, start=1):
        title = item.get("title") or _agent_title(str(item.get("agent") or "agent"))
        lines.append(f"{index}. **{title}**：{item.get('content', '')}")
    return "\n".join(lines)


def _agent_title(agent: str) -> str:
    return {
        "aggressive": "激进处置 Agent",
        "conservative": "保守安全 Agent",
        "decision": "裁决 Agent",
    }.get(agent, agent)


def _try_text(
    prompt: str,
    *,
    system: str,
    state: Dict[str, Any],
    max_tokens: int,
) -> str | None:
    if try_complete_text is None:
        return None
    return try_complete_text(
        prompt,
        system=system,
        outputs_dir=state.get("outputs_dir") or "outputs",
        temperature=0.15,
        max_tokens=max_tokens,
    )


def _fallback_question_answer(question: str, state: Dict[str, Any]) -> str:
    if any(term in question for term in ["依据", "标准", "行标", "引用"]):
        return "\n".join(
            [
                "## 引用依据说明",
                "",
                "当前问题可从最终方案的“关键引用摘录”和右侧“引用来源”复核。",
                "",
                state.get("compliance_report", "合规审核未返回详细内容，需复核 Wiki 标准页。"),
            ]
        )
    if any(term in question for term in ["为什么", "直接", "优先", "不用"]):
        return "\n".join(
            [
                "## 方案逻辑说明",
                "",
                "当前方案不直接跳到强化处置，是因为事故处置需要先确认井控、循环、鱼顶状态、落鱼尺寸和工具通过性。",
                "",
                "- 若这些条件未确认，直接下工具可能扩大卡阻或破坏鱼顶。",
                "- 若循环稳定、鱼顶清洁、尺寸扣型确认，可以把直接打捞作为条件化提速窗口。",
                "- 所有拉力、扭矩、震击等参数仍需现场设计确认。",
            ]
        )
    return "\n".join(
        [
            "## 追问回答",
            "",
            "这个问题应结合当前方案和已知事故信息判断。若问题涉及新增现场事实，请补充井况、循环、鱼顶、扣型、工具通过性等信息后触发方案修订。",
        ]
    )


def _changed_fields(old: Dict[str, Any], new: Dict[str, Any]) -> str:
    labels = {**FIELD_LABELS, "inclination": "井斜角", "thread_type": "扣型"}
    changed = []
    for key, label in labels.items():
        if old.get(key) != new.get(key) and new.get(key):
            changed.append(f"{label}={new.get(key)}")
    return "、".join(changed)


def _planning_delta(
    node: Callable[[Dict[str, Any]], Dict[str, Any]],
    plan_key: str,
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    return _delta_node(node, (plan_key,))


def _delta_node(
    node: Callable[[Dict[str, Any]], Dict[str, Any]],
    keys: tuple[str, ...],
) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Run an existing full-state node and emit only the changed fields.

    The serial fallback can keep using the simpler nodes that return full state.
    LangGraph parallel fan-out needs smaller deltas so evidence from the two
    planning branches can be merged without duplicating the incoming state.
    """

    def wrapped(state: Dict[str, Any]) -> Dict[str, Any]:
        before_evidence = list(state.get("evidence", []))
        result = node(state)
        delta = {key: result[key] for key in keys if key in result}
        after_evidence = list(result.get("evidence", []))
        new_evidence = _new_items(before_evidence, after_evidence)
        if new_evidence:
            delta["evidence"] = new_evidence
        return delta

    return wrapped


def _new_items(before: list[Dict[str, Any]], after: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    if len(after) >= len(before) and after[: len(before)] == before:
        return after[len(before) :]
    seen = {_fingerprint(item) for item in before}
    return [item for item in after if _fingerprint(item) not in seen]


def _fingerprint(item: Dict[str, Any]) -> tuple[Any, ...]:
    return (
        item.get("source_type"),
        item.get("source_page"),
        item.get("page_no"),
        item.get("clause"),
        item.get("summary"),
        item.get("quote"),
    )


def solve_accident(
    description: str,
    *,
    wiki_dir: str = "wiki",
    outputs_dir: str = "outputs",
    archive: bool = True,
) -> Dict[str, Any]:
    """Run the online pipeline and return the final state."""

    if archive:
        return converse_accident(
            description,
            {},
            wiki_dir=wiki_dir,
            outputs_dir=outputs_dir,
        )

    initial: Dict[str, Any] = {
        "accident": {"raw_description": description},
        "wiki_dir": wiki_dir,
        "outputs_dir": outputs_dir,
        "evidence": [],
        **_llm_state(outputs_dir),
    }
    graph = SequentialGraph(PIPELINE[:-1])
    return graph.invoke(initial)


def _llm_state(outputs_dir: str) -> Dict[str, Any]:
    if load_llm_config is None:
        return {
            "llm_enabled": False,
            "llm_provider": "",
            "llm_fallback_reason": "LLM wrapper is unavailable.",
        }
    config = load_llm_config(outputs_dir=outputs_dir)
    reason = ""
    if not config.enabled:
        reason = "LLM is disabled."
    elif not config.api_key:
        reason = "LLM API key is not configured."
    elif not config.model:
        reason = "LLM model is not configured."
    return {
        "llm_enabled": config.configured,
        "llm_provider": config.provider,
        "llm_fallback_reason": reason,
    }


def query_wiki_or_solve(question: str, *, wiki_dir: str = "wiki") -> Dict[str, Any]:
    """CLI-friendly query hook.

    Worker 1 owns retrieval quality. Until that layer exists, this reuses the
    same stable state shape and marks the result as unarchived.
    """

    return solve_accident(question, wiki_dir=wiki_dir, archive=False)
