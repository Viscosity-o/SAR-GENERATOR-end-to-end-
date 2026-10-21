"""
Model Training Module for SAR Classification (Agent 1).
Trains XGBoost Classifier (multi:softprob) + RandomForest Regressor on data_engineered.csv
and saves the canonical pre-trained model to model.pkl.
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure workspace root is in sys.path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import xgboost as xgb

try:
    from orchestration.feature_engineering import FEATURE_COLUMNS
except ImportError:
    from feature_engineering import FEATURE_COLUMNS


TYPOLOGY_NAMES: List[str] = [
    "Structuring",
    "Rapid Movement",
    "Funnel Account",
    "TBML",
    "Shell Company",
    "Round Tripping",
]

TYPOLOGY_CSV_COLS: List[str] = [
    "typology_structuring",
    "typology_rapid_movement",
    "typology_funnel_account",
    "typology_trade_based",
    "typology_shell_company",
    "typology_round_tripping",
]


class PredictionArray(np.ndarray):
    """
    Custom 1D numpy array representing typology probabilities that also
    faithfully implements the prompt's indexing convention:
      predictions[1] -> sar_worthy probability (binary non-SAR vs SAR)
      predictions[2] -> risk_score / priority score (0-1)
      np.argmax(predictions) -> index (0..5) of predicted typology
      np.max(predictions) -> confidence score (0-1)
    """

    def __new__(
        cls,
        input_array: Union[List[float], np.ndarray],
        sar_prob: float = 0.0,
        risk_score: float = 0.5,
    ):
        obj = np.asarray(input_array, dtype=float).view(cls)
        obj._sar_prob = float(sar_prob)
        obj._risk_score = float(risk_score)
        return obj

    def __getitem__(self, item: Any) -> Any:
        # Standard integer indexing overrides for prompt contract
        if item == 1 and not isinstance(item, slice):
            return self._sar_prob
        elif item == 2 and not isinstance(item, slice):
            return self._risk_score
        return super().__getitem__(item)


class SARModel:
    """
    Unified SAR Classification and Planning Model.
    Wraps:
      1. xgb_strength: XGBoost multi:softprob (3 classes: 0=WEAK, 1=MEDIUM, 2=STRONG)
      2. rf_priority: RandomForestRegressor for continuous priority/risk score (0-1)
      3. xgb_typology: XGBoost multi:softprob for the 6 SAR typologies
    """

    def __init__(
        self,
        xgb_strength: xgb.XGBClassifier,
        rf_priority: RandomForestRegressor,
        xgb_typology: xgb.XGBClassifier,
        feature_names: List[str],
    ):
        self.xgb_strength = xgb_strength
        self.rf_priority = rf_priority
        self.xgb_typology = xgb_typology
        self.feature_names = feature_names

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> List[PredictionArray]:
        """
        Predicts probabilities for a batch or single vector X.
        Returns a list of PredictionArray objects that satisfy:
          predictions = model.predict_proba(X)[0]
          sar_worthy = (predictions[1] > 0.5)
          confidence_score = float(np.max(predictions))
          typology = TYPOLOGIES[np.argmax(predictions)]
          risk_score = float(predictions[2]) if predictions.shape[0] > 2 else 0.5
        """
        if isinstance(X, pd.DataFrame):
            X_df = X[self.feature_names]
        else:
            X_df = pd.DataFrame(X, columns=self.feature_names)

        # 1. Strength probabilities (3 classes: 0=WEAK, 1=MEDIUM, 2=STRONG)
        strength_probs = self.xgb_strength.predict_proba(X_df)

        # 2. Priority/risk score via RandomForest (0-1)
        risk_scores = self.rf_priority.predict(X_df)
        risk_scores = np.clip(risk_scores, 0.0, 1.0)

        # 3. Typology probabilities (6 typologies)
        typology_probs = self.xgb_typology.predict_proba(X_df)

        results: List[PredictionArray] = []
        for i in range(len(X_df)):
            p_weak = float(strength_probs[i][0])
            p_sar = float(1.0 - p_weak)  # probability of SAR (MEDIUM or STRONG)
            r_score = float(risk_scores[i])
            typ_probs = np.copy(typology_probs[i])

            if p_sar <= 0.5:
                # If non-SAR, damp typology confidence
                typ_probs = typ_probs * 0.1

            pred_arr = PredictionArray(
                input_array=typ_probs,
                sar_prob=p_sar,
                risk_score=r_score,
            )
            results.append(pred_arr)

        return results

    def predict_case(self, X: Union[pd.DataFrame, np.ndarray]) -> Dict[str, Any]:
        """
        High-level prediction helper returning a structured dictionary.
        """
        predictions = self.predict_proba(X)[0]
        sar_worthy = bool(predictions[1] > 0.5)
        confidence_score = float(np.max(predictions))
        best_idx = int(np.argmax(predictions))
        typology = TYPOLOGY_NAMES[best_idx] if sar_worthy else "Unknown"
        risk_score = float(predictions[2]) if predictions.shape[0] > 2 else 0.5

        return {
            "sar_worthy": sar_worthy,
            "confidence_score": round(confidence_score, 4),
            "typology": typology,
            "risk_score": round(risk_score, 4),
            "all_typology_scores": {
                name: round(float(prob), 4)
                for name, prob in zip(TYPOLOGY_NAMES, np.asarray(predictions))
            },
        }


def train_models(
    csv_path: str = "data_engineered.csv",
    save_path: Optional[str] = None,
) -> SARModel:
    """
    Trains the XGBoost + RandomForest models on data_engineered.csv (7,000 rows).
    Saves the trained SARModel to model.pkl.
    """
    print(f"Loading training data from {csv_path}...")
    df = pd.read_csv(csv_path)

    # 1. Feature matrix (33 features)
    X = df[FEATURE_COLUMNS].copy()

    # 2. Target 1: Strength class (0=WEAK, 1=MEDIUM, 2=STRONG)
    # 0 = non-SAR (sar_worthy=0)
    # 1 = SAR with moderate risk (sar_worthy=1 & binary_risk_flag_count < 2)
    # 2 = SAR with strong risk (sar_worthy=1 & binary_risk_flag_count >= 2)
    strength = np.zeros(len(df), dtype=int)
    strength[(df["sar_worthy"] == 1) & (df["binary_risk_flag_count"] < 2)] = 1
    strength[(df["sar_worthy"] == 1) & (df["binary_risk_flag_count"] >= 2)] = 2

    # 3. Target 2: Priority/risk score continuous regression (0-1)
    priority_target = np.clip(
        0.35 * df["kyc_risk_score"]
        + 0.25 * df["fund_exit_ratio"]
        + 0.15 * df["burst_score"]
        + 0.15 * df["high_risk_combined"]
        + 0.10 * (df["alert_tier"] / 4.0),
        0.0,
        1.0,
    )

    # 4. Target 3: 6 Typology classes
    typology_target = np.argmax(df[TYPOLOGY_CSV_COLS].values, axis=1)

    print("Fitting XGBoost Strength Classifier (multi:softprob, num_class=3)...")
    xgb_strength = xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=3,
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mlogloss",
    )
    xgb_strength.fit(X, strength)

    print("Fitting RandomForest Priority Regressor (0-1)...")
    rf_priority = RandomForestRegressor(
        n_estimators=60,
        max_depth=6,
        random_state=42,
        n_jobs=-1,
    )
    rf_priority.fit(X, priority_target)

    print("Fitting XGBoost Typology Classifier (multi:softprob, num_class=6)...")
    xgb_typology = xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=6,
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mlogloss",
    )
    # Train typology classifier on SAR cases (where typologies are defined)
    sar_indices = df["sar_worthy"] == 1
    xgb_typology.fit(X[sar_indices], typology_target[sar_indices])

    model = SARModel(
        xgb_strength=xgb_strength,
        rf_priority=rf_priority,
        xgb_typology=xgb_typology,
        feature_names=FEATURE_COLUMNS,
    )

    # Save destinations
    destinations = [
        save_path or os.path.join(os.path.dirname(__file__), "model.pkl"),
        os.path.join(os.getcwd(), "model.pkl"),
    ]

    for dest in set(destinations):
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        joblib.dump(model, dest)
        print(f"Model successfully saved to {dest}")

    return model


if __name__ == "__main__":
    try:
        from orchestration.model_training import train_models as _tm
        _tm()
    except Exception:
        train_models()

