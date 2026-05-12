"""Shared state schemas for the drilling accident agent graph."""

from __future__ import annotations

from operator import add
from typing import Annotated, Dict, List, Optional, TypedDict


class AccidentInput(TypedDict, total=False):
    raw_description: str
    well_type: str
    depth: float
    fish_type: str
    fish_description: str
    mud_type: str
    additional_info: str
    missing_fields: List[str]


class EvidenceItem(TypedDict):
    source_type: str
    source_page: str
    source_pdf: str
    page_no: Optional[int]
    clause: Optional[str]
    quote: str
    summary: str


class AgentState(TypedDict, total=False):
    accident: AccidentInput
    evidence: Annotated[List[EvidenceItem], add]
    similar_case_items: List[Dict]
    similar_cases: str
    aggressive_plan: str
    conservative_plan: str
    compliance_report: str
    final_plan: str
    debate_rounds: List[Dict]
    wiki_pages_used: List[str]
    confidence_score: float
    output_path: str
