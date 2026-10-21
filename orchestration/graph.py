"""
LangGraph Orchestration Graph for the 6-Agent SAR Pipeline.
Defines nodes, conditional edges, revision loops, and compiles the executable graph.
"""

from typing import Literal
from langgraph.graph import END, START, StateGraph

from orchestration.state import SARAgentState
from orchestration.agent1_ingestion import agent1_ingestion
from orchestration.masking_agent import masking_agent
from orchestration.agent2_planner import agent2_planner
from orchestration.agent3_evidence import agent3_evidence
from orchestration.agent5_narrative import agent5_narrative
from orchestration.agent6_compliance import agent6_compliance, route_after_agent6


def route_sar_worthy(state: SARAgentState) -> Literal["masking_agent", "__end__"]:
    """
    Conditional routing after Agent 1 (Ingestion & ML):
      IF sar_worthy == True -> proceed to Masking Agent
      ELSE -> exit pipeline to END (no LLM cost)
    """
    if state.get("sar_worthy", False):
        return "masking_agent"
    return END


def route_compliance_decision(state: SARAgentState) -> Literal["agent5_narrative", "__end__"]:
    """
    Conditional routing after Agent 6 (Compliance):
      IF quality_score >= 0.60 or revision_count >= 3 -> exit pipeline to END
      ELSE -> loop back to Agent 5 for narrative revision
    """
    decision = route_after_agent6(state)
    if decision == "agent5_narrative":
        return "agent5_narrative"
    return END


def create_sar_graph() -> StateGraph:
    """
    Constructs the complete 6-agent LangGraph StateGraph:
      START -> agent1_ingestion
      agent1_ingestion -> (sar_worthy? Yes: masking_agent, No: END)
      masking_agent -> agent2_planner
      agent2_planner -> agent3_evidence
      agent3_evidence -> agent5_narrative
      agent5_narrative -> agent6_compliance
      agent6_compliance -> (quality >= 0.60? Yes: END, No: agent5_narrative)
    """
    builder = StateGraph(SARAgentState)

    # 1. Register all agent nodes
    builder.add_node("agent1_ingestion", agent1_ingestion)
    builder.add_node("masking_agent", masking_agent)
    builder.add_node("agent2_planner", agent2_planner)
    builder.add_node("agent3_evidence", agent3_evidence)
    builder.add_node("agent5_narrative", agent5_narrative)
    builder.add_node("agent6_compliance", agent6_compliance)

    # 2. Add edges & entry point
    builder.add_edge(START, "agent1_ingestion")

    # Conditional edge: Agent 1 -> sar_worthy check
    builder.add_conditional_edges(
        "agent1_ingestion",
        route_sar_worthy,
        {
            "masking_agent": "masking_agent",
            END: END,
        },
    )

    # Deterministic linear sequence
    builder.add_edge("masking_agent", "agent2_planner")
    builder.add_edge("agent2_planner", "agent3_evidence")
    builder.add_edge("agent3_evidence", "agent5_narrative")
    builder.add_edge("agent5_narrative", "agent6_compliance")

    # Conditional edge: Agent 6 compliance loop
    builder.add_conditional_edges(
        "agent6_compliance",
        route_compliance_decision,
        {
            "agent5_narrative": "agent5_narrative",
            END: END,
        },
    )

    return builder


# Pre-compiled application instance for high-performance reuse
sar_pipeline_app = create_sar_graph().compile()
