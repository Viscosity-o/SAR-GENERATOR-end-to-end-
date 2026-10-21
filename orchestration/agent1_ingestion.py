"""
Agent 1: Ingestion & ML Classification Module.
Ingests SAR case data from Supabase/S3 or local CSV, aggregates the 33 canonical
features, loads the pre-trained XGBoost model, and classifies the case as SAR-worthy.
"""

import os
import sys
from typing import Any, Dict, List, Optional
import joblib
import numpy as np
import pandas as pd

# Ensure workspace root is in sys.path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from orchestration.state import SARAgentState
from orchestration.feature_engineering import (
    FEATURE_COLUMNS,
    extract_features_from_structured_case,
    extract_features_from_csv,
)

# Cached model instance for low-latency inference across calls
_CACHED_MODEL: Optional[Any] = None


def get_model(model_path: Optional[str] = None) -> Any:
    """
    Loads and caches the pre-trained SARModel from model.pkl.
    Checks multiple search paths; trains once if missing.
    """
    global _CACHED_MODEL
    if _CACHED_MODEL is not None:
        return _CACHED_MODEL

    candidate_paths: List[str] = []
    if model_path:
        candidate_paths.append(model_path)
    candidate_paths.extend([
        os.path.join(os.getcwd(), "model.pkl"),
        os.path.join(os.path.dirname(__file__), "model.pkl"),
        os.path.join(workspace_root, "model.pkl"),
        os.path.join(workspace_root, "orchestration", "model.pkl"),
    ])

    for p in candidate_paths:
        if os.path.isfile(p):
            try:
                _CACHED_MODEL = joblib.load(p)
                return _CACHED_MODEL
            except Exception:
                pass

    # If model file is not found, train once
    from orchestration.model_training import train_models
    csv_train_path = os.path.join(workspace_root, "data_engineered.csv")
    _CACHED_MODEL = train_models(csv_path=csv_train_path)
    return _CACHED_MODEL


def agent1_ingestion(state: SARAgentState) -> SARAgentState:
    """
    Agent 1 (Ingestion & ML Classification).

    Steps:
      1. Resolve input data from:
         a) Pre-existing structured_case dict (from backend ingestion service)
         b) S3 / Supabase storage bucket & case_id (downloads & parses 4 files)
         c) Local transactions_csv path
      2. Feature Aggregation: Extracts 33 canonical features.
      3. ML Inference: Predicts sar_worthy, confidence_score, typology, and risk_score.
      4. Output to state: Returns updated SARAgentState.
    """
    error_log: List[str] = list(state.get("error_log", []))
    case_id = state.get("case_id", "UNKNOWN_CASE")
    s3_bucket = state.get("s3_bucket", "").strip()
    s3_prefix = state.get("s3_prefix", "").strip()
    transactions_csv = state.get("transactions_csv", "").strip()
    structured_case = state.get("structured_case") or {}

    features_df: Optional[pd.DataFrame] = None

    # -------------------------------------------------------------------------
    # STEP 1: Load / Resolve Input Data
    # -------------------------------------------------------------------------
    # Option A: structured_case is already present in state
    if structured_case and isinstance(structured_case, dict) and len(structured_case) > 0:
        try:
            features_df = extract_features_from_structured_case(structured_case)
        except Exception as e:
            error_log.append(f"Feature extraction from structured_case failed: {str(e)}")

    # Option B: S3 / Supabase storage bucket is provided
    if features_df is None and s3_bucket:
        try:
            # Attempt to use the backend DataIngestionService
            try:
                from backend.services.ingestion_service import DataIngestionService
                service = DataIngestionService(bucket_name=s3_bucket)
                downloaded_case = service.ingest_case(case_id=case_id, bucket_name=s3_bucket)
                structured_case = downloaded_case
                features_df = extract_features_from_structured_case(structured_case)
            except Exception as backend_err:
                # Fallback to boto3 S3 if AWS S3 was configured
                import boto3
                s3_client = boto3.client("s3")
                prefix = s3_prefix or f"{case_id}/"
                manifest = [
                    "account_transactions.csv",
                    "transaction_alerts.csv",
                    "customer_kyc.json",
                    "case_management.json",
                ]
                raw_files: Dict[str, Any] = {}
                for fname in manifest:
                    key = f"{prefix.rstrip('/')}/{fname}"
                    try:
                        obj = s3_client.get_object(Bucket=s3_bucket, Key=key)
                        raw_files[fname] = obj["Body"].read()
                    except Exception:
                        pass

                if raw_files:
                    # Construct minimal structured_case from raw files
                    structured_case = {
                        "case_id": case_id,
                        "raw_files": list(raw_files.keys()),
                    }
                    features_df = extract_features_from_structured_case(structured_case)
                else:
                    raise backend_err
        except Exception as e:
            error_log.append(f"Ingestion from storage ({s3_bucket}) failed: {str(e)}")

    # Option C: Local transactions_csv fallback
    if features_df is None and transactions_csv:
        try:
            if os.path.isfile(transactions_csv):
                features_df = extract_features_from_csv(transactions_csv)
            else:
                error_log.append(f"Transactions CSV path not found: {transactions_csv}")
        except Exception as e:
            error_log.append(f"Reading transactions_csv failed: {str(e)}")

    # Option D: Neither available or all failed
    if features_df is None or features_df.empty:
        error_msg = f"No valid input data could be resolved for case '{case_id}'"
        error_log.append(error_msg)
        return {
            **state,
            "sar_worthy": False,
            "confidence_score": 0.0,
            "typology": "Unknown",
            "risk_score": 0.0,
            "structured_case": structured_case,
            "error_log": error_log,
        }

    # -------------------------------------------------------------------------
    # STEP 2 & 3: Feature Aggregation & Pre-Trained Model Inference
    # -------------------------------------------------------------------------
    try:
        model = get_model()
        X = features_df[FEATURE_COLUMNS]

        # Single case feature vector (1 × 33 features)
        predictions = model.predict_proba(X)[0]

        sar_worthy = bool(predictions[1] > 0.5)  # binary: non-SAR vs SAR
        confidence_score = float(np.max(predictions))
        typologies = [
            "Structuring",
            "Rapid Movement",
            "Funnel Account",
            "TBML",
            "Shell Company",
            "Round Tripping",
        ]
        best_idx = int(np.argmax(predictions))
        typology = typologies[best_idx] if (sar_worthy and best_idx < len(typologies)) else "Unknown"
        risk_score = float(predictions[2]) if hasattr(predictions, "shape") and predictions.shape[0] > 2 else 0.5

    except Exception as e:
        error_log.append(f"ML classification failed: {str(e)}")
        sar_worthy = False
        confidence_score = 0.0
        typology = "Unknown"
        risk_score = 0.0

    # -------------------------------------------------------------------------
    # STEP 4: Output to State
    # -------------------------------------------------------------------------
    return {
        **state,
        "sar_worthy": sar_worthy,
        "confidence_score": round(confidence_score, 4),
        "typology": typology,
        "risk_score": round(risk_score, 4),
        "structured_case": structured_case,
        "error_log": error_log,
    }


def route_after_agent1(state: SARAgentState) -> str:
    """
    Routing (Conditional Edge) after Agent 1:
      IF sar_worthy == False:
        -> Route to END (exit pipeline, no LLM calls)
      ELSE:
        -> Route to Agent 2 (PLANNER)
    """
    return "agent2_planner" if state.get("sar_worthy", False) else "end"
