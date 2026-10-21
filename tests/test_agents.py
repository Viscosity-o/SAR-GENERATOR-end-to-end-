"""
Comprehensive Test Suite for Agent 1 (Ingestion & ML Classification)
and Agent 2 (Planner).
"""

import os
import sys
import unittest
import pandas as pd
import numpy as np

# Ensure workspace root is in sys.path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from orchestration.state import SARAgentState
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
)
from orchestration.agent1_ingestion import (
    agent1_ingestion,
    route_after_agent1,
    get_model,
)
from orchestration.agent2_planner import (
    agent2_planner,
    route_after_agent2,
    build_case_summary,
)
from orchestration.pipeline import (
    run_call_1,
    run_call_2,
    run_pipeline,
)


class TestAgent1AndAgent2(unittest.TestCase):

    def setUp(self):
        self.csv_path = os.path.join(workspace_root, "data_engineered.csv")
        self.model = get_model()

    def test_01_feature_columns_count_and_order(self):
        """Verify exactly 33 features matching specification."""
        self.assertEqual(len(FEATURE_COLUMNS), 33)
        df_csv = pd.read_csv(self.csv_path, nrows=1)
        for col in FEATURE_COLUMNS:
            self.assertIn(col, df_csv.columns)

    def test_02_model_loading_and_inference(self):
        """Verify model loads and prediction format conforms to exact prompt snippet."""
        df = pd.read_csv(self.csv_path, nrows=1)
        X = df[FEATURE_COLUMNS]
        predictions = self.model.predict_proba(X)[0]

        sar_worthy = bool(predictions[1] > 0.5)
        confidence_score = float(np.max(predictions))
        typology = [
            "Structuring", "Rapid Movement", "Funnel Account",
            "TBML", "Shell Company", "Round Tripping"
        ][np.argmax(predictions)]
        risk_score = float(predictions[2]) if hasattr(predictions, "shape") and predictions.shape[0] > 2 else 0.5

        self.assertIsInstance(sar_worthy, bool)
        self.assertIsInstance(confidence_score, float)
        self.assertIn(typology, TYPOLOGY_NAMES)
        self.assertIsInstance(risk_score, float)
        self.assertTrue(0.0 <= risk_score <= 1.0)

    def test_03_agent1_ingestion_with_structured_case_dict(self):
        """
        Verify Agent 1 consumes structured_case dictionary (produced by ingestion layer)
        and outputs correct state fields.
        """
        structured_case = {
            "case_id": "CASE-TEST-INGESTION-001",
            "sar_system_version": "1.0",
            "financial_activity": {
                "transaction_count": 25,
                "total_volume": 4500000.0,
                "burst_score": 0.85,
                "fund_exit_ratio": 0.92,
                "txn_velocity": 12.0,
                "time_to_first_outbound_minutes": 45.0,
                "international_counterparty_flag": 1,
                "transactions": [
                    {"amount": 180000.0, "direction": "in", "counterparty": "CP-1"},
                    {"amount": 175000.0, "direction": "out", "counterparty": "CP-2"},
                ],
            },
            "subject_profile": {
                "kyc_risk_score": 0.88,
                "pep_flag": 1,
                "high_risk_country_flag": 1,
                "historical_sar_flag": 1,
                "account_age_days": 180.0,
            },
            "case_details": {
                "alert_count": 7,
            },
        }

        initial_state: SARAgentState = {
            "case_id": "CASE-TEST-INGESTION-001",
            "structured_case": structured_case,
            "error_log": [],
        }

        result_state = agent1_ingestion(initial_state)

        self.assertIn("sar_worthy", result_state)
        self.assertTrue(result_state["sar_worthy"])
        self.assertGreater(result_state["confidence_score"], 0.0)
        self.assertIn(result_state["typology"], TYPOLOGY_NAMES)
        self.assertTrue(0.0 <= result_state["risk_score"] <= 1.0)
        self.assertEqual(len(result_state["error_log"]), 0)

        # Routing check
        route = route_after_agent1(result_state)
        self.assertEqual(route, "agent2_planner")

    def test_04_agent1_with_local_csv_fallback(self):
        """Verify Agent 1 resolves local CSV path fallback."""
        initial_state: SARAgentState = {
            "case_id": "CASE-CSV-FALLBACK",
            "transactions_csv": self.csv_path,
            "error_log": [],
        }
        result_state = agent1_ingestion(initial_state)
        self.assertIn("sar_worthy", result_state)
        self.assertIsInstance(result_state["sar_worthy"], bool)

    def test_05_agent1_with_invalid_input_routes_to_end(self):
        """Verify Agent 1 with no inputs logs error and exits early to end."""
        initial_state: SARAgentState = {
            "case_id": "EMPTY-CASE",
            "error_log": [],
        }
        result_state = agent1_ingestion(initial_state)
        self.assertFalse(result_state["sar_worthy"])
        self.assertEqual(result_state["confidence_score"], 0.0)
        self.assertEqual(result_state["typology"], "Unknown")
        self.assertGreater(len(result_state["error_log"]), 0)

        route = route_after_agent1(result_state)
        self.assertEqual(route, "end")

    def test_06_agent2_planner_deterministic_module_selection(self):
        """Verify Agent 2 selects exact modules for all 6 typologies deterministically."""
        expected_modules = {
            "Structuring": ["structuring_analysis", "velocity_analysis", "account_behaviour_analysis"],
            "Rapid Movement": ["velocity_analysis", "network_analysis", "account_behaviour_analysis"],
            "TBML": ["international_analysis", "network_analysis", "account_behaviour_analysis"],
            "Funnel Account": ["network_analysis", "velocity_analysis", "account_behaviour_analysis"],
            "Shell Company": ["network_analysis", "kyc_escalation", "account_behaviour_analysis"],
            "Round Tripping": ["international_analysis", "velocity_analysis", "account_behaviour_analysis"],
            "Unknown": ["account_behaviour_analysis"],
        }

        for typ, expected in expected_modules.items():
            state: SARAgentState = {
                "case_id": f"TEST-{typ}",
                "sar_worthy": True,
                "confidence_score": 0.85,
                "typology": typ,
                "risk_score": 0.65,
                "structured_case": {"transactions": [{"amount": 100}]},
            }
            res = agent2_planner(state)
            self.assertEqual(res["plan"]["active_modules"], expected)

    def test_07_agent2_planner_enrichment_decision_logic(self):
        """Verify enrichment rule-based triggers."""
        # 1. Complex typologies require enrichment
        for typ in ["TBML", "Shell Company", "Round Tripping"]:
            state: SARAgentState = {
                "case_id": "TEST-ENRICH-TYP",
                "sar_worthy": True,
                "confidence_score": 0.85,
                "typology": typ,
                "risk_score": 0.50,
                "structured_case": {},
            }
            res = agent2_planner(state)
            self.assertTrue(res["requires_enrichment"])
            self.assertTrue(res["plan"]["requires_enrichment"])

        # 2. PEP requires enrichment
        state_pep: SARAgentState = {
            "case_id": "TEST-ENRICH-PEP",
            "sar_worthy": True,
            "confidence_score": 0.85,
            "typology": "Structuring",
            "risk_score": 0.50,
            "structured_case": {"customer": {"pep_flag": 1}},
        }
        res_pep = agent2_planner(state_pep)
        self.assertTrue(res_pep["requires_enrichment"])

        # 3. High risk (>0.80) requires enrichment
        state_high_risk: SARAgentState = {
            "case_id": "TEST-ENRICH-RISK",
            "sar_worthy": True,
            "confidence_score": 0.85,
            "typology": "Structuring",
            "risk_score": 0.85,
            "structured_case": {"customer": {"pep_flag": 0}},
        }
        res_hr = agent2_planner(state_high_risk)
        self.assertTrue(res_hr["requires_enrichment"])

        # 4. Low risk Structuring with non-PEP does not require enrichment
        state_no_enrich: SARAgentState = {
            "case_id": "TEST-NO-ENRICH",
            "sar_worthy": True,
            "confidence_score": 0.85,
            "typology": "Structuring",
            "risk_score": 0.50,
            "structured_case": {"customer": {"pep_flag": 0}},
        }
        res_no = agent2_planner(state_no_enrich)
        self.assertFalse(res_no["requires_enrichment"])

    def test_08_agent2_planner_priority_tiers(self):
        """Verify priority tier computation: >0.70 HIGH, >0.40 MEDIUM, <=0.40 LOW."""
        for score, expected_priority in [(0.90, "HIGH"), (0.55, "MEDIUM"), (0.25, "LOW")]:
            state: SARAgentState = {
                "case_id": "TEST-PRIORITY",
                "sar_worthy": True,
                "confidence_score": 0.85,
                "typology": "Structuring",
                "risk_score": score,
                "structured_case": {},
            }
            res = agent2_planner(state)
            self.assertEqual(res["plan"]["priority"], expected_priority)

    def test_09_end_to_end_pipeline(self):
        """Verify full pipeline execution of Agent 1 and Agent 2."""
        structured_case = {
            "case_id": "CASE-PIPELINE-001",
            "financial_activity": {
                "transaction_count": 30,
                "total_volume": 12000000.0,
                "burst_score": 0.90,
                "fund_exit_ratio": 0.95,
                "txn_velocity": 18.0,
                "time_to_first_outbound_minutes": 20.0,
                "international_counterparty_flag": 1,
            },
            "subject_profile": {
                "kyc_risk_score": 0.85,
                "pep_flag": 1,
                "high_risk_country_flag": 1,
                "historical_sar_flag": 1,
                "account_age_days": 120.0,
            },
            "case_details": {
                "alert_count": 8,
            },
        }

        final_state = run_pipeline(
            case_id="CASE-PIPELINE-001",
            structured_case=structured_case,
        )

        self.assertTrue(final_state["sar_worthy"])
        self.assertIn("plan", final_state)
        self.assertIn("active_modules", final_state["plan"])
        self.assertIn("priority", final_state["plan"])
        self.assertEqual(route_after_agent2(final_state), "end")


if __name__ == "__main__":
    unittest.main()
