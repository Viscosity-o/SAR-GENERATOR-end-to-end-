"""
Orchestration Package for 6-Agent SAR Pipeline using LangGraph.
"""

import os
import sys

# Ensure workspace root is always available in sys.path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from orchestration.state import SARAgentState
from orchestration.llm_client import invoke_llm, invoke_llm_json
from orchestration.feature_engineering import (
    FEATURE_COLUMNS,
    extract_features_from_structured_case,
    extract_features_from_csv,
    calculate_alert_tier,
    calculate_kyc_risk_tier,
    calculate_fund_exit_tier,
)
from orchestration.model_training import (
    SARModel,
    PredictionArray,
    TYPOLOGY_NAMES,
    train_models,
)
from orchestration.agent1_ingestion import (
    agent1_ingestion,
    route_after_agent1,
    get_model,
)
from orchestration.masking_agent import (
    masking_agent,
    PIIMasker,
)
from orchestration.agent2_planner import (
    agent2_planner,
    route_after_agent2,
    build_case_summary,
    VALID_MODULES,
)
from orchestration.agent3_evidence import (
    agent3_evidence,
    evaluate_stage1_rules,
    generate_cognitive_event_flow,
)
from orchestration.agent5_narrative import (
    agent5_narrative,
    mock_rag_retrieval,
    compile_context_tree,
    generate_sar_draft,
)
from orchestration.agent6_compliance import (
    agent6_compliance,
    route_after_agent6,
    validate_structure,
)
from orchestration.graph import (
    create_sar_graph,
    sar_pipeline_app,
)
from orchestration.pipeline import (
    run_call_1_ingest,
    run_call_2_analyse,
    run_full_langgraph_pipeline,
)

__all__ = [
    "SARAgentState",
    "FEATURE_COLUMNS",
    "extract_features_from_structured_case",
    "extract_features_from_csv",
    "calculate_alert_tier",
    "calculate_kyc_risk_tier",
    "calculate_fund_exit_tier",
    "SARModel",
    "PredictionArray",
    "TYPOLOGY_NAMES",
    "train_models",
    "invoke_llm",
    "invoke_llm_json",
    "agent1_ingestion",
    "route_after_agent1",
    "get_model",
    "masking_agent",
    "PIIMasker",
    "agent2_planner",
    "route_after_agent2",
    "build_case_summary",
    "VALID_MODULES",
    "agent3_evidence",
    "evaluate_stage1_rules",
    "generate_cognitive_event_flow",
    "agent5_narrative",
    "mock_rag_retrieval",
    "compile_context_tree",
    "generate_sar_draft",
    "agent6_compliance",
    "route_after_agent6",
    "validate_structure",
    "create_sar_graph",
    "sar_pipeline_app",
    "run_call_1_ingest",
    "run_call_2_analyse",
    "run_full_langgraph_pipeline",
]
