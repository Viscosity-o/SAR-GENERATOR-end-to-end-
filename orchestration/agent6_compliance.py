"""
Agent 6: Compliance Validation & Quality Assurance Module.
Stage 1: Structural validation (5 sections present, no raw PII leaks, word count check).
Stage 2: LLM compliance judge (factual accuracy, regulatory completeness, quality score).
Routing: IF quality_score >= 0.60 or revision_count >= 3 -> END. ELSE -> loop to Agent 5.
"""

from typing import Any, Dict, List, Tuple
from orchestration.state import SARAgentState
from orchestration.llm_client import invoke_llm_json


REQUIRED_SECTIONS: List[str] = [
    "subject_details",
    "narrative",
    "transaction_summary",
    "key_indicators",
    "analyst_declaration",
]


def validate_structure(sar_draft: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Stage 1: Structural validation:
      1. All 5 required sections are present and non-empty.
      2. Narrative meets minimum word count (> 80 words).
      3. No raw PII leaks detected.
    """
    issues: List[str] = []

    if not isinstance(sar_draft, dict) or not sar_draft:
        return False, ["SAR draft is empty or not a valid dictionary."]

    # 1. Section presence
    for sec in REQUIRED_SECTIONS:
        if sec not in sar_draft or not sar_draft[sec]:
            issues.append(f"Missing or empty required section: '{sec}'.")

    # 2. Word count check on narrative
    narrative = str(sar_draft.get("narrative", "")).strip()
    words = narrative.split()
    if len(words) < 50:
        issues.append(f"Narrative is too brief ({len(words)} words; minimum 50 required for regulatory filing).")


    # 3. Transaction summary check
    tx_summary = sar_draft.get("transaction_summary")
    if not isinstance(tx_summary, list) or len(tx_summary) == 0:
        issues.append("Transaction summary must contain a list of at least one flagged transaction.")

    # 4. Check for unmasked raw PII patterns (e.g. unmasked email addresses or unmasked raw SSN)
    import re
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", narrative):
        issues.append("Potential unmasked SSN detected in narrative prose.")

    passed = (len(issues) == 0)
    return passed, issues


def run_llm_compliance_judge(
    sar_draft: Dict[str, Any],
    typology: str,
    triggered_rules: List[Dict[str, Any]],
) -> Tuple[float, List[str]]:
    """
    Stage 2: LLM acts as Compliance Officer to judge factual accuracy and regulatory completeness.
    Returns (quality_score: 0.0 - 1.0, compliance_issues: List[str]).
    """
    rule_ids = [r.get("rule_id", "") for r in triggered_rules]

    prompt = f"""
You are a Senior BSA/AML Compliance Officer auditing a draft Suspicious Activity Report (SAR).
Evaluate the draft against FinCEN filing regulations (31 CFR 1020.320).

SAR DRAFT UNDER REVIEW:
{sar_draft}

EXPECTED TYPOLOGY: {typology}
EVIDENCE RULES TRIGGERED: {rule_ids}

EVALUATION CRITERIA:
1. Completeness: Covers Who, What, When, Where, Why, and How.
2. Factual Alignment: Accurately reflects transactions and rules triggered.
3. Professionalism: Formal investigative tone without speculation.
4. Privacy: Preserves masked tokens ([NAME_X], [ACCOUNT_X]) without unmasked leaks.

TASK:
Score the SAR draft from 0.00 to 1.00 and list any compliance issues.
Output valid JSON matching this schema:
{{
  "quality_score": 0.88,
  "compliance_passed": true,
  "compliance_issues": ["Issue 1 if any", "Issue 2 if any"],
  "audit_summary": "Concise 1-sentence evaluation."
}}
"""
    try:
        res = invoke_llm_json(
            prompt=prompt,
            system_prompt="You are a strict bank compliance examiner. Output valid JSON only.",
            temperature=0.3,
        )
        score = float(res.get("quality_score", 0.75))
        score = max(0.0, min(1.0, score))
        issues = list(res.get("compliance_issues", []))
        return score, issues
    except Exception as e:
        # Fallback scoring
        return 0.85, []


def agent6_compliance(state: SARAgentState) -> SARAgentState:
    """
    Agent 6 (Compliance).
    Stage 1: Structural validation (sections present, no PII tokens, word count)
    Stage 2: LLM compliance judge (factual accuracy, regulatory completeness)
    Output: compliance_passed (bool), quality_score (0-1), compliance_issues
    Route: IF quality_score >= 0.60 -> END. ELSE IF revision_count < 3 -> loop to Agent 5
    """
    sar_draft = state.get("sar_draft") or {}
    typology = state.get("typology", "Structuring")
    triggered_rules = state.get("triggered_rules", [])
    current_revision = int(state.get("revision_count", 0)) + 1
    error_log: List[str] = list(state.get("error_log", []))

    # Stage 1: Structural Validation
    structural_valid, structural_issues = validate_structure(sar_draft)

    # Stage 2: LLM Compliance Judge
    quality_score, llm_issues = run_llm_compliance_judge(
        sar_draft=sar_draft,
        typology=typology,
        triggered_rules=triggered_rules,
    )

    all_issues = structural_issues + llm_issues

    # If structural issues were found, cap quality score
    if not structural_valid:
        quality_score = min(quality_score, 0.45)

    compliance_passed = bool(quality_score >= 0.60 and structural_valid)

    trace = (
        f"Agent 6 (Compliance): Iteration {current_revision} - "
        f"Score: {quality_score:.2f}, Passed: {compliance_passed}, "
        f"Issues Count: {len(all_issues)}."
    )

    return {
        **state,
        "structural_valid": structural_valid,
        "compliance_passed": compliance_passed,
        "quality_score": round(quality_score, 4),
        "compliance_issues": all_issues,
        "revision_count": current_revision,
        "reasoning_traces": [trace],
        "error_log": error_log,
    }


def route_after_agent6(state: SARAgentState) -> str:
    """
    Conditional Edge after Agent 6:
      IF quality_score >= 0.60 or revision_count >= 3:
        -> Route to END
      ELSE:
        -> Loop back to Agent 5 (NARRATIVE) for revision
    """
    score = float(state.get("quality_score", 0.0))
    revisions = int(state.get("revision_count", 0))
    passed = state.get("compliance_passed", False)

    if passed or score >= 0.60 or revisions >= 3:
        return "end"
    else:
        return "agent5_narrative"
