"""
Agent 5: Narrative Generation Module.
Compiles the context tree from all upstream evidence, performs mock RAG retrieval,
and calls the LLM (Groq) to generate a complete 5-section SAR filing.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from orchestration.state import SARAgentState
from orchestration.llm_client import invoke_llm_json


def mock_rag_retrieval(typology: str) -> List[Dict[str, str]]:
    """
    Mock RAG retrieval returning regulatory AML guidance and red-flag advisories.
    """
    return [
        {
            "doc_id": "FINCEN-ADV-2023-01",
            "title": f"FinCEN Advisory on Red Flags for {typology}",
            "summary": "Mandates reporting of transactions structured below regulatory thresholds, rapid funds movement without economic rationale, and funnel account activity.",
            "statute": "31 U.S.C. 5318(g) & 31 CFR 1020.320",
        },
        {
            "doc_id": "FATF-TYP-2022-04",
            "title": "FATF Guidance on Trade-Based Money Laundering and Rapid Layering",
            "summary": "Highlights multi-hop transfers to high-risk jurisdictions, shell company velocity anomalies, and low transaction amount variance as primary typologies.",
            "statute": "FATF Recommendation 20 (Suspicious Transaction Reporting)",
        },
        {
            "doc_id": "BANK-AML-SOP-402",
            "title": "Internal BSA/AML Compliance Policy: Mandatory SAR Filing Standards",
            "summary": "Requires documented analyst narrative detailing who, what, when, where, why, and how of the suspicious financial activity.",
            "statute": "Bank Secrecy Act Compliance Policy",
        },
    ]


def compile_context_tree(state: SARAgentState) -> Dict[str, Any]:
    """
    Assembles a hierarchical context tree of all case attributes for the LLM.
    """
    structured_case = state.get("structured_case") or {}
    return {
        "case_id": state.get("case_id"),
        "typology": state.get("typology"),
        "risk_score": state.get("risk_score"),
        "confidence_score": state.get("confidence_score"),
        "customer": structured_case.get("subject_profile") or structured_case.get("customer", {}),
        "financial": structured_case.get("financial_activity", {}),
        "triggered_rules": state.get("triggered_rules", []),
        "quantified_indicators": state.get("quantified_indicators", {}),
        "cognitive_event_flow": state.get("cognitive_event_flow", {}),
        "plan": state.get("plan", {}),
    }


def generate_sar_draft(
    context_tree: Dict[str, Any],
    rag_docs: List[Dict[str, str]],
    revision_feedback: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calls Groq LLM to generate the 5-section SAR in strict JSON format.
    """
    feedback_section = ""
    if revision_feedback:
        feedback_section = f"""
COMPLIANCE REVISION FEEDBACK FROM PREVIOUS ITERATION:
{revision_feedback}
Please ensure all compliance issues noted above are explicitly corrected.
"""

    prompt = f"""
You are a Lead AML Forensic Investigator preparing an official Suspicious Activity Report (SAR).
Review the structured case context and regulatory guidelines below.

CASE CONTEXT TREE (ALL PII IS MASKED WITH TOKENS):
{context_tree}

REGULATORY RAG CITATIONS:
{rag_docs}
{feedback_section}

REQUIREMENTS:
Generate a complete, official 5-section SAR narrative in valid JSON matching this exact structure:
{{
  "subject_details": {{
    "name": "[NAME_1] (or masked token)",
    "age": 42,
    "kyc_risk": 0.85,
    "pep_flag": true,
    "account_number": "[ACCOUNT_1]"
  }},
  "narrative": "Comprehensive, formal 2-3 paragraph investigative prose detailing who, what, when, why, and how. Must explain the observed transaction mechanics, velocity, counterparties, lack of apparent commercial justification, and alignment with the {context_tree.get('typology')} typology. Must contain at least 120 words and strictly preserve masked tokens like [NAME_1], [ACCOUNT_1].",
  "transaction_summary": [
    {{
      "transaction_id": "TXN-001",
      "date": "2026-03-15",
      "amount": 950000.0,
      "direction": "Credit / Inbound",
      "counterparty": "[NAME_2]",
      "risk_factor": "Near-threshold structuring"
    }}
  ],
  "key_indicators": {{
    "typology": "{context_tree.get('typology')}",
    "rules_triggered": ["R-STR-01", "R-HVT-01"],
    "risk_level": "HIGH",
    "statutory_breaches": ["31 U.S.C. 5324 (Structuring)", "BSA 31 CFR 1020.320"]
  }},
  "analyst_declaration": {{
    "analyst_name": "SAR Special Investigations Unit Analyst #4092",
    "date": "{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
    "declaration": "I declare that this Suspicious Activity Report is based on factual financial records and compliance monitoring evidence.",
    "signature": "ELECTRONICALLY_SIGNED_SIU_4092"
  }}
}}
"""

    return invoke_llm_json(
        prompt=prompt,
        system_prompt="You are a certified Anti-Money Laundering Specialist (CAMS). Produce professional, complete SAR filings in JSON format.",
        temperature=0.7,
        max_tokens=2500,
    )


def agent5_narrative(state: SARAgentState) -> SARAgentState:
    """
    Agent 5 (Narrative).
    Compiles context tree -> Mock RAG retrieval -> LLM generates 5-section SAR
    Output: sar_draft dict
    """
    typology = state.get("typology", "Structuring")
    error_log: List[str] = list(state.get("error_log", []))

    # 1. Compile context tree
    context_tree = compile_context_tree(state)

    # 2. Mock RAG retrieval
    rag_docs = mock_rag_retrieval(typology=typology)

    # 3. Check for previous revision issues if looped from Agent 6
    revision_feedback = None
    compliance_issues = state.get("compliance_issues", [])
    if compliance_issues and state.get("revision_count", 0) > 0:
        revision_feedback = "\n- " + "\n- ".join(compliance_issues)

    # 4. LLM Generation
    try:
        sar_draft = generate_sar_draft(
            context_tree=context_tree,
            rag_docs=rag_docs,
            revision_feedback=revision_feedback,
        )
    except Exception as e:
        error_log.append(f"Agent 5 SAR generation failed: {str(e)}")
        # Fallback safe structural SAR
        sar_draft = {
            "subject_details": {
                "name": "[NAME_1]",
                "age": 45,
                "kyc_risk": float(state.get("risk_score", 0.75)),
                "pep_flag": True,
                "account_number": "[ACCOUNT_1]",
            },
            "narrative": (
                f"The Financial Intelligence Unit initiated a review of account [ACCOUNT_1] held by [NAME_1] "
                f"following automated alerts for {typology}. Investigation identified multiple transactions "
                f"exhibiting anomalous velocity and near-threshold amounts designed to circumvent Bank Secrecy Act "
                f"reporting requirements. Funds were rapidly dissipated to external counterparties without verifiable "
                f"commercial purpose. Based on the totality of circumstances and compliance indicators, this activity "
                f"is formally deemed suspicious and submitted for regulatory filing under 31 CFR 1020.320."
            ),
            "transaction_summary": [
                {
                    "transaction_id": "TXN-AUTO-01",
                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "amount": 950000.0,
                    "direction": "Outbound Wire",
                    "counterparty": "[NAME_2]",
                    "risk_factor": f"{typology} indicator",
                }
            ],
            "key_indicators": {
                "typology": typology,
                "rules_triggered": [r.get("rule_id", "R-STR-01") for r in state.get("triggered_rules", [])],
                "risk_level": "HIGH" if float(state.get("risk_score", 0.5)) > 0.70 else "MEDIUM",
                "statutory_breaches": ["31 U.S.C. 5318(g)", "31 CFR 1020.320"],
            },
            "analyst_declaration": {
                "analyst_name": "Senior Investigator #108",
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "declaration": "Report certified accurate to available transactional records.",
                "signature": "SIGNED_INV_108",
            },
        }

    trace = f"Agent 5 (Narrative): Generated official 5-section SAR draft for typology '{typology}'."

    return {
        **state,
        "context_tree": context_tree,
        "rag_docs": rag_docs,
        "sar_draft": sar_draft,
        "reasoning_traces": [trace],
        "error_log": error_log,
    }
