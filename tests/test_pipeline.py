"""
End-to-End Test Suite for the 6-Agent SAR Pipeline using LangGraph and FastAPI.
Tests Masking Agent, Agent 3 (Evidence), Agent 5 (Narrative), Agent 6 (Compliance),
LangGraph DAG execution, and the 2-call microservice endpoints.
"""

import os
import sys
import unittest
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Ensure workspace root is in sys.path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from orchestration.state import SARAgentState
from orchestration.masking_agent import masking_agent, PIIMasker
from orchestration.agent3_evidence import agent3_evidence, evaluate_stage1_rules
from orchestration.agent5_narrative import agent5_narrative, mock_rag_retrieval
from orchestration.agent6_compliance import agent6_compliance, validate_structure
from orchestration.graph import sar_pipeline_app
from orchestration.pipeline import run_call_1_ingest, run_call_2_analyse


class TestSixAgentPipeline(unittest.TestCase):

    def setUp(self):
        self.sample_raw_case = {
            "case_id": "CASE-TEST-2026-999",
            "subject_profile": {
                "name": "Alexander Sterling",
                "dob": "1978-04-12",
                "ssn": "987-65-4321",
                "kyc_risk_score": 0.88,
                "pep_flag": 1,
                "high_risk_country_flag": 1,
                "historical_sar_flag": 1,
                "account_age_days": 240,
                "email": "a.sterling@offshorecapital.org",
            },
            "financial_activity": {
                "transaction_count": 8,
                "total_volume": 7600000.0,
                "burst_score": 0.92,
                "fund_exit_ratio": 0.96,
                "txn_velocity": 14.5,
                "time_to_first_outbound_minutes": 35.0,
                "international_counterparty_flag": 1,
                "transactions": [
                    {
                        "transaction_id": "TX-01",
                        "amount": 950000.0,
                        "direction": "in",
                        "counterparty": "Apex Holdings Ltd",
                        "account_number": "440192837465",
                    },
                    {
                        "transaction_id": "TX-02",
                        "amount": 950000.0,
                        "direction": "in",
                        "counterparty": "Apex Holdings Ltd",
                        "account_number": "440192837465",
                    },
                    {
                        "transaction_id": "TX-03",
                        "amount": 940000.0,
                        "direction": "out",
                        "counterparty": "Global Wire Services Zurich",
                        "account_number": "CH93000012345678",
                        "is_international": True,
                    },
                    {
                        "transaction_id": "TX-04",
                        "amount": 940000.0,
                        "direction": "out",
                        "counterparty": "Offshore Cayman Express",
                        "account_number": "KY88000987654321",
                        "is_international": True,
                    },
                ],
            },
            "case_details": {
                "alert_count": 6,
                "high_risk_country_flag": 1,
            },
        }

    def test_01_masking_agent_pii_vault(self):
        """Test Masking Agent replaces PII and stores in PostgreSQL."""
        state: SARAgentState = {
            "case_id": "CASE-TEST-2026-999",
            "structured_case": self.sample_raw_case,
            "error_log": [],
            "reasoning_traces": [],
        }

        masked_state = masking_agent(state)
        masked_case = masked_state["structured_case"]
        mapping = masked_state["pii_mapping"]

        # Assert raw name and account are replaced
        self.assertNotIn("Alexander Sterling", str(masked_case))
        self.assertNotIn("440192837465", str(masked_case))
        self.assertIn("[NAME_", str(masked_case))
        self.assertIn("[ACCOUNT_", str(masked_case))
        self.assertIn("Alexander Sterling", mapping)

        # Assert PostgreSQL table has the records
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM pii_masking_vault WHERE case_id = %s;", ("CASE-TEST-2026-999",))
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            self.assertGreater(count, 0)

    def test_02_agent3_evidence_deterministic_rules_and_cognitive_flow(self):
        """Test Agent 3 executes all 8 deterministic rules and synthesizes cognitive flow."""
        triggered, indicators = evaluate_stage1_rules(
            structured_case=self.sample_raw_case,
            risk_score=0.88,
        )

        rule_ids = [r["rule_id"] for r in triggered]
        # Should trigger Structuring, Velocity, Rapid Pass-Through, Multi-Hop, Cross-Border, and FATF
        self.assertIn("R-STR-01", rule_ids)  # 900K-1M band
        self.assertIn("R-HVT-01", rule_ids)  # Velocity > 0.75
        self.assertIn("R-HVT-02", rule_ids)  # Outbound wire < 3.5h
        self.assertIn("R-IWT-01", rule_ids)  # Cross-border wire
        self.assertIn("R-IWT-02", rule_ids)  # FATF jurisdiction

        # Test full Agent 3 node with LLM cognitive flow
        state: SARAgentState = {
            "case_id": "CASE-TEST-2026-999",
            "structured_case": self.sample_raw_case,
            "typology": "Structuring",
            "risk_score": 0.88,
            "error_log": [],
            "reasoning_traces": [],
        }

        res = agent3_evidence(state)
        self.assertIn("cognitive_event_flow", res)
        flow = res["cognitive_event_flow"]
        self.assertIn("event_sequence", flow)
        self.assertIn("fund_flow", flow)
        self.assertIn("hypothesis", flow)

    def test_03_agent5_narrative_generates_5_sections(self):
        """Test Agent 5 generates 5-section SAR narrative with mock RAG."""
        state: SARAgentState = {
            "case_id": "CASE-TEST-2026-999",
            "structured_case": self.sample_raw_case,
            "typology": "Structuring",
            "risk_score": 0.88,
            "confidence_score": 0.94,
            "triggered_rules": [
                {"rule_id": "R-STR-01", "rule_name": "Near-Threshold Structuring Band", "evidence": "2 txns in 900K-1M band"},
                {"rule_id": "R-HVT-01", "rule_name": "High Velocity", "evidence": "Velocity 14.5"},
            ],
            "quantified_indicators": {"total_volume": 7600000.0, "transaction_count": 8},
            "cognitive_event_flow": {
                "event_sequence": [{"step": 1, "description": "Rapid placement and layering"}],
                "fund_flow": "Inbound credits immediately wired offshore.",
                "hypothesis": "Classic high-value structuring.",
            },
            "error_log": [],
            "reasoning_traces": [],
        }

        res = agent5_narrative(state)
        self.assertIn("sar_draft", res)
        draft = res["sar_draft"]

        # Check all 5 required sections
        self.assertIn("subject_details", draft)
        self.assertIn("narrative", draft)
        self.assertIn("transaction_summary", draft)
        self.assertIn("key_indicators", draft)
        self.assertIn("analyst_declaration", draft)

        # Check narrative length
        self.assertGreater(len(str(draft["narrative"]).split()), 40)

    def test_04_agent6_compliance_judge_and_validation(self):
        """Test Agent 6 structural and compliance auditing."""
        draft = {
            "subject_details": {"name": "[NAME_1]", "kyc_risk": 0.85},
            "narrative": (
                "The Financial Intelligence Unit detected structured layering activities "
                "originating from account [ACCOUNT_1] held by [NAME_1]. A total of eight transactions "
                "were executed within a compressed forty-eight hour window, with multiple transfers "
                "intentionally clustered between $940,000 and $950,000 to circumvent regulatory thresholds. "
                "Funds were subsequently wired to offshore jurisdictions without commercial justification. "
                "This behavior violates 31 U.S.C. 5324 and constitutes reportable structuring activity."
            ),
            "transaction_summary": [{"transaction_id": "TXN-01", "amount": 950000.0, "direction": "in"}],
            "key_indicators": {"typology": "Structuring", "rules_triggered": ["R-STR-01", "R-HVT-01"]},
            "analyst_declaration": {"analyst_name": "Senior Investigator", "date": "2026-03-20"},
        }

        state: SARAgentState = {
            "case_id": "CASE-COMPLIANCE-TEST",
            "sar_draft": draft,
            "typology": "Structuring",
            "triggered_rules": [{"rule_id": "R-STR-01"}],
            "revision_count": 0,
            "error_log": [],
            "reasoning_traces": [],
        }

        res = agent6_compliance(state)
        self.assertTrue(res["structural_valid"])
        self.assertGreater(res["quality_score"], 0.0)
        self.assertIn("compliance_issues", res)

    def test_05_microservice_call1_and_call2(self):
        """Test Call 1 (/ingest) and Call 2 (/analyse) microservice contracts."""
        # Call 1
        res_call1 = run_call_1_ingest(
            case_id="CASE-MICRO-001",
            structured_case=self.sample_raw_case,
        )
        self.assertEqual(res_call1["status"], "success")
        self.assertTrue(res_call1["sar_worthy"])
        self.assertIn("typology", res_call1)

        # Call 2
        res_call2 = run_call_2_analyse(
            case_id="CASE-MICRO-001",
            structured_case=self.sample_raw_case,
            typology=res_call1["typology"],
            risk_score=res_call1["risk_score"],
            confidence_score=res_call1["confidence_score"],
            sar_worthy=res_call1["sar_worthy"],
        )
        self.assertEqual(res_call2["status"], "success")
        self.assertIn("sar_draft", res_call2)
        self.assertTrue(res_call2["compliance_passed"])
        self.assertGreaterEqual(res_call2["quality_score"], 0.60)
        self.assertIn("plan", res_call2)

    def test_06_full_langgraph_pipeline_execution(self):
        """Test full 6-agent LangGraph execution end-to-end."""
        initial_state: SARAgentState = {
            "case_id": "CASE-LANGGRAPH-FULL",
            "structured_case": self.sample_raw_case,
            "error_log": [],
            "reasoning_traces": [],
            "triggered_rules": [],
            "revision_count": 0,
        }

        final_state = sar_pipeline_app.invoke(initial_state)

        # Verify end-to-end state propagation
        self.assertTrue(final_state["sar_worthy"])
        self.assertIn("[NAME_", str(final_state["structured_case"]))  # PII masked
        self.assertIn("plan", final_state)
        self.assertGreater(len(final_state["triggered_rules"]), 0)
        self.assertIn("sar_draft", final_state)
        self.assertTrue(final_state["compliance_passed"])


if __name__ == "__main__":
    unittest.main()
