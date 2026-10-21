"""
SAR Agent State Definition
Contract for the 6-agent SAR generation pipeline using LangGraph.
"""

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class SARAgentState(TypedDict, total=False):
    """
    Single unified state contract for the 6-agent SAR pipeline.
    Accumulating fields use Annotated[list, operator.add] for LangGraph state merging.
    """

    # --- Call 1 Inputs & Classification (Agent 1) ---
    case_id: str
    s3_bucket: str
    s3_prefix: str
    transactions_csv: str
    sar_worthy: bool
    confidence_score: float
    typology: str
    risk_score: float

    # --- Call 2 Ingestion & Masking ---
    structured_case: Dict[str, Any]  # Masked case passed downstream
    raw_case: Dict[str, Any]         # Original unmasked case
    pii_mapping: Dict[str, str]      # Original -> Masked token mapping

    # --- Agent 2 (Planner) Outputs ---
    plan: Dict[str, Any]
    requires_enrichment: bool

    # --- Agent 3 (Evidence) Outputs ---
    triggered_rules: Annotated[List[Dict[str, Any]], operator.add]
    quantified_indicators: Dict[str, Any]
    cognitive_event_flow: Dict[str, Any]

    # --- Agent 5 (Narrative) Outputs ---
    context_tree: Dict[str, Any]
    rag_docs: List[Dict[str, Any]]
    sar_draft: Dict[str, Any]

    # --- Agent 6 (Compliance) Outputs ---
    structural_valid: bool
    compliance_passed: bool
    quality_score: float
    compliance_issues: List[str]
    revision_count: int

    # --- Accumulating Audit & Control Flow ---
    reasoning_traces: Annotated[List[str], operator.add]
    error_log: Annotated[List[str], operator.add]
