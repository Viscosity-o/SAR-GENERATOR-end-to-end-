"""
Agent 2: Planner Module (Routing & Module Selection).
Evaluates Agent 1 classification outputs and structured_case metadata,
builds a compact case summary, selects deterministic analysis modules,
and decides if external data enrichment is required.
"""

from typing import Any, Dict, List, Optional
from orchestration.state import SARAgentState


VALID_MODULES: List[str] = [
    "structuring_analysis",
    "velocity_analysis",
    "network_analysis",
    "international_analysis",
    "kyc_escalation",
    "account_behaviour_analysis",
]


def build_case_summary(structured_case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts key metrics from structured_case WITHOUT LLM:
      - customer_risk_rating
      - pep_flag
      - n_transactions
      - international_txn_flag
      - alert_count
      - max_velocity_score
      - high_risk_country_flag
    """
    if not structured_case:
        return {
            "customer_risk_rating": 0.5,
            "pep_flag": False,
            "n_transactions": 0,
            "international_txn_flag": False,
            "alert_count": 0,
            "max_velocity_score": 0.0,
            "high_risk_country_flag": False,
        }

    # Support both schema conventions:
    # Scheme A (raw): customer, accounts, transactions, banks
    # Scheme B (ingestion layer): subject_profile, financial_activity, case_details, supporting_activity
    # Scheme A (raw): customer, accounts, transactions, banks
    # Scheme B (ingestion layer): subject_profile, financial_activity, case_details, supporting_activity
    customer = structured_case.get("customer") or structured_case.get("subject_profile") or {}
    if isinstance(customer, list):
        customer = customer[0] if customer else {}
    if not isinstance(customer, dict):
        customer = {}

    financial = structured_case.get("financial_activity") or {}
    if isinstance(financial, list):
        financial = financial[0] if financial else {}
    if not isinstance(financial, dict):
        financial = {}

    case_details = structured_case.get("case_details") or {}
    if isinstance(case_details, list):
        case_details = case_details[0] if case_details else {}
    if not isinstance(case_details, dict):
        case_details = {}

    supporting = structured_case.get("supporting_activity") or {}
    if isinstance(supporting, list):
        supporting = {"records": supporting}
    elif not isinstance(supporting, dict):
        supporting = {}

    tx_list: List[Dict[str, Any]] = (
        financial.get("transactions", [])
        or structured_case.get("transactions", [])
        or []
    )

    # 1. customer_risk_rating
    raw_rr = (
        customer.get("risk_rating")
        or customer.get("kyc_risk_score")
        or customer.get("risk_score")
        or customer.get("kyc_tier")
        or 0.5
    )
    if isinstance(raw_rr, (int, float)):
        customer_risk_rating = float(raw_rr)
    elif isinstance(raw_rr, str):
        rr_lower = raw_rr.lower()
        if any(w in rr_lower for w in ["crit", "high", "tier_1", "tier 1", "enhanced", "escalated"]):
            customer_risk_rating = 0.85
        elif any(w in rr_lower for w in ["med", "moderate", "tier_2", "tier 2"]):
            customer_risk_rating = 0.50
        elif any(w in rr_lower for w in ["low", "tier_3", "tier 3"]):
            customer_risk_rating = 0.20
        else:
            try:
                customer_risk_rating = float(raw_rr.replace("%", "").strip())
            except ValueError:
                customer_risk_rating = 0.5
    else:
        customer_risk_rating = 0.5

    # 2. pep_flag
    pep_val = customer.get("pep_flag") or customer.get("is_pep", False) or customer.get("pep_status", False)
    pep_flag = bool(pep_val == 1 or pep_val is True or any(w in str(pep_val).lower() for w in ["true", "yes", "politically exposed"]))

    # 3. n_transactions
    n_transactions = len(tx_list) or int(financial.get("transaction_count", 0))

    # 4. international_txn_flag
    intl_flag_val = (
        financial.get("international_counterparty_flag")
        or structured_case.get("international_txn_flag")
    )
    if intl_flag_val is None:
        # Check transaction rows
        intl_flag = any(
            bool(tx.get("is_international") or tx.get("cross_border") or tx.get("foreign_currency") or tx.get("counterparty_country"))
            for tx in tx_list
        )
    else:
        intl_flag = bool(intl_flag_val == 1 or str(intl_flag_val).lower() == "true")

    # 5. alert_count
    alert_ids = case_details.get("alert_ids") or []
    alert_count = int(
        case_details.get("alert_count")
        or (len(alert_ids) if isinstance(alert_ids, list) else 0)
        or len(supporting.get("records", []))
        or structured_case.get("alert_count", 0)
    )

    # 6. max_velocity_score
    max_velocity_score = float(
        financial.get("txn_velocity")
        or financial.get("max_velocity_score")
        or structured_case.get("max_velocity_score", 0.0)
    )

    # 7. high_risk_country_flag
    hr_val = (
        customer.get("high_risk_country_flag")
        or case_details.get("high_risk_country_flag")
        or structured_case.get("high_risk_country_flag", False)
    )
    high_risk_country_flag = bool(hr_val == 1 or hr_val is True or str(hr_val).lower() == "true")

    return {
        "customer_risk_rating": round(customer_risk_rating, 4),
        "pep_flag": pep_flag,
        "n_transactions": n_transactions,
        "international_txn_flag": intl_flag,
        "alert_count": alert_count,
        "max_velocity_score": round(max_velocity_score, 4),
        "high_risk_country_flag": high_risk_country_flag,
    }


def agent2_planner(state: SARAgentState) -> SARAgentState:
    """
    Agent 2 (Planner).

    Steps:
      1. Extract compact case summary without LLM.
      2. Route to active analysis modules deterministically based on typology.
      3. Decide if enrichment is needed based on typology, PEP status, and risk_score.
      4. Build plan dict with priority and rationale.
      5. Return updated SARAgentState.
    """
    case_id = state.get("case_id", "UNKNOWN_CASE")
    typology = state.get("typology", "Unknown")
    risk_score = float(state.get("risk_score", 0.5))
    structured_case = state.get("structured_case") or {}

    # -------------------------------------------------------------------------
    # STEP 1: Build Case Summary (Compact, No LLM)
    # -------------------------------------------------------------------------
    case_summary = build_case_summary(structured_case)
    pep_flag = case_summary.get("pep_flag", False)

    # -------------------------------------------------------------------------
    # STEP 2: Route to Analysis Modules (Rule-Based, No LLM)
    # -------------------------------------------------------------------------
    if typology == "Structuring":
        active_modules = ["structuring_analysis", "velocity_analysis", "account_behaviour_analysis"]
    elif typology == "Rapid Movement":
        active_modules = ["velocity_analysis", "network_analysis", "account_behaviour_analysis"]
    elif typology == "TBML":
        active_modules = ["international_analysis", "network_analysis", "account_behaviour_analysis"]
    elif typology == "Funnel Account":
        active_modules = ["network_analysis", "velocity_analysis", "account_behaviour_analysis"]
    elif typology == "Shell Company":
        active_modules = ["network_analysis", "kyc_escalation", "account_behaviour_analysis"]
    elif typology == "Round Tripping":
        active_modules = ["international_analysis", "velocity_analysis", "account_behaviour_analysis"]
    else:
        active_modules = ["account_behaviour_analysis"]  # baseline always active

    if risk_score > 0.70:
        priority = "HIGH"
    elif risk_score > 0.40:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    # -------------------------------------------------------------------------
    # STEP 3: Decide Enrichment Need (Rule-Based, No LLM)
    # -------------------------------------------------------------------------
    requires_enrichment = False
    if typology in ["TBML", "Shell Company", "Round Tripping"]:
        requires_enrichment = True  # international / complex typologies require external data
    elif pep_flag:
        requires_enrichment = True  # PEP cases require sanctions screening
    elif risk_score > 0.80:
        requires_enrichment = True  # high-risk cases require enrichment

    # -------------------------------------------------------------------------
    # STEP 4: Build Plan Dict
    # -------------------------------------------------------------------------
    plan: Dict[str, Any] = {
        "case_id": case_id,
        "active_modules": active_modules,
        "priority": priority,
        "requires_enrichment": requires_enrichment,
        "rationale": f"Typology={typology}, Risk={risk_score:.2f}, Modules={len(active_modules)}",
        "case_summary": case_summary,
    }

    # -------------------------------------------------------------------------
    # STEP 5: Output to State
    # -------------------------------------------------------------------------
    return {
        **state,
        "plan": plan,
        "requires_enrichment": requires_enrichment,
    }


def route_after_agent2(state: SARAgentState) -> str:
    """
    Routing (Conditional Edge) after Agent 2:
      For now (scope limited to Agent 1 & Agent 2 only):
      returns "end".
    """
    return "end"
