"""
SAR Orchestration Pipeline Runner.
Coordinates Call 1 (/ingest), Call 2 (/analyse), and full LangGraph DAG execution.
"""

from typing import Any, Dict, Optional
from orchestration.state import SARAgentState
from orchestration.agent1_ingestion import agent1_ingestion, route_after_agent1
from orchestration.masking_agent import masking_agent
from orchestration.agent2_planner import agent2_planner
from orchestration.agent3_evidence import agent3_evidence
from orchestration.agent5_narrative import agent5_narrative
from orchestration.agent6_compliance import agent6_compliance
from orchestration.graph import sar_pipeline_app


def run_call_1_ingest(
    case_id: str,
    s3_bucket: str = "",
    s3_prefix: str = "",
    transactions_csv: str = "",
    structured_case: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Call 1 (/ingest):
      Loads data -> Extracts 33 features -> XGBoost classify.
      Returns: {sar_worthy, typology, confidence_score, risk_score, case_id}
    """
    initial_state: SARAgentState = {
        "case_id": case_id,
        "s3_bucket": s3_bucket,
        "s3_prefix": s3_prefix,
        "transactions_csv": transactions_csv,
        "structured_case": structured_case or {},
        "error_log": [],
        "reasoning_traces": [],
    }

    state_after_agent1 = agent1_ingestion(initial_state)

    return {
        "status": "success",
        "case_id": case_id,
        "sar_worthy": state_after_agent1.get("sar_worthy", False),
        "typology": state_after_agent1.get("typology", "Unknown"),
        "confidence_score": state_after_agent1.get("confidence_score", 0.0),
        "risk_score": state_after_agent1.get("risk_score", 0.0),
        "structured_case": state_after_agent1.get("structured_case", {}),
        "error_log": state_after_agent1.get("error_log", []),
    }


def run_call_2_analyse(
    case_id: str,
    structured_case: Dict[str, Any],
    typology: str = "Structuring",
    risk_score: float = 0.75,
    confidence_score: float = 0.90,
    sar_worthy: bool = True,
) -> Dict[str, Any]:
    """
    Call 2 (/analyse):
      Runs Masking Agent -> Agent 2 -> Agent 3 -> Agent 5 -> Agent 6 (with revision loop).
      Returns: {case_id, sar_draft, compliance_passed, quality_score, plan, triggered_rules}
    """
    state: SARAgentState = {
        "case_id": case_id,
        "structured_case": structured_case,
        "raw_case": structured_case,
        "typology": typology,
        "risk_score": risk_score,
        "confidence_score": confidence_score,
        "sar_worthy": sar_worthy,
        "error_log": [],
        "reasoning_traces": [],
        "triggered_rules": [],
        "revision_count": 0,
    }

    # Step 1: Masking Agent
    state = masking_agent(state)

    # Step 2: Agent 2 Planner
    state = agent2_planner(state)

    # Step 3: Agent 3 Evidence Analyzer
    state = agent3_evidence(state)

    # Step 4: Agent 5 Narrative Generator & Agent 6 Compliance Judge loop
    while True:
        state = agent5_narrative(state)
        state = agent6_compliance(state)

        passed = state.get("compliance_passed", False)
        revisions = state.get("revision_count", 0)

        if passed or revisions >= 3:
            break

    return {
        "status": "success",
        "case_id": case_id,
        "sar_draft": state.get("sar_draft", {}),
        "compliance_passed": state.get("compliance_passed", False),
        "quality_score": state.get("quality_score", 0.0),
        "compliance_issues": state.get("compliance_issues", []),
        "plan": state.get("plan", {}),
        "triggered_rules": state.get("triggered_rules", []),
        "quantified_indicators": state.get("quantified_indicators", {}),
        "cognitive_event_flow": state.get("cognitive_event_flow", {}),
        "revision_count": state.get("revision_count", 1),
        "reasoning_traces": state.get("reasoning_traces", []),
    }


def run_full_langgraph_pipeline(
    case_id: str,
    s3_bucket: str = "",
    s3_prefix: str = "",
    transactions_csv: str = "",
    structured_case: Optional[Dict[str, Any]] = None,
) -> SARAgentState:
    """
    Runs the complete 6-Agent LangGraph StateGraph pipeline end-to-end.
    """
    initial_state: SARAgentState = {
        "case_id": case_id,
        "s3_bucket": s3_bucket,
        "s3_prefix": s3_prefix,
        "transactions_csv": transactions_csv,
        "structured_case": structured_case or {},
        "raw_case": structured_case or {},
        "error_log": [],
        "reasoning_traces": [],
        "triggered_rules": [],
        "revision_count": 0,
    }

    final_state = sar_pipeline_app.invoke(initial_state)
    return final_state


# Aliases for backward compatibility
run_call_1 = run_call_1_ingest
run_call_2 = run_call_2_analyse
run_pipeline = run_full_langgraph_pipeline

