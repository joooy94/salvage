"""LangGraph orchestration for the online accident disposition pipeline."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, TypedDict

from .agents import (
    accident_parser_node,
    aggressive_plan_node,
    case_matcher_node,
    compliance_checker_node,
    conservative_plan_node,
    decision_maker_node,
    output_archiver_node,
)


try:
    from .state import AgentState as BaseAgentState
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


class AgentState(BaseAgentState, total=False):
    wiki_dir: str
    outputs_dir: str
    question: str
    raw_description: str


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

    initial: Dict[str, Any] = {
        "accident": {"raw_description": description},
        "wiki_dir": wiki_dir,
        "outputs_dir": outputs_dir,
        "evidence": [],
    }
    if not archive:
        graph = SequentialGraph(PIPELINE[:-1])
    else:
        graph = build_graph()
    return graph.invoke(initial)


def query_wiki_or_solve(question: str, *, wiki_dir: str = "wiki") -> Dict[str, Any]:
    """CLI-friendly query hook.

    Worker 1 owns retrieval quality. Until that layer exists, this reuses the
    same stable state shape and marks the result as unarchived.
    """

    return solve_accident(question, wiki_dir=wiki_dir, archive=False)
