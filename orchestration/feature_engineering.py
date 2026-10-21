"""
Feature Engineering Module for SAR Classification (Agent 1).
Extracts, aggregates, and transforms raw case data into the exact 33-feature
vector required by the XGBoost classification model.
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

# The exact 33 canonical feature names matching data_engineered.csv in specified order
FEATURE_COLUMNS: List[str] = [
    # Group A — Transaction volume & shape (7)
    "total_txn_amount_cbrt",
    "avg_txn_amount_cbrt",
    "std_txn_amount_cbrt",
    "txn_count_log",
    "txn_amount_cv",
    "max_to_avg_txn_ratio",
    "fund_exit_ratio",
    # Group B — Speed & urgency (4)
    "burst_score",
    "time_to_first_outbound_minutes_log",
    "txn_velocity_log",
    "burst_per_age",
    # Group C — Counterparty network (5)
    "distinct_counterparties_log",
    "incoming_sources_count_log",
    "counterparty_diversity_score",
    "counterparty_to_txn_ratio",
    "incoming_to_outgoing_ratio",
    # Group D — Alert signals (4)
    "alert_count",
    "alert_density",
    "alert_tier",
    "kyc_x_alert",
    # Group E — Jurisdiction & risk flags (7)
    "international_counterparty_flag",
    "high_risk_country_flag",
    "pep_flag",
    "kyc_risk_score",
    "kyc_risk_tier",
    "historical_sar_flag",
    "high_risk_combined",
    # Group F — Interaction & tier features (6)
    "burst_x_exit",
    "hr_country_x_exit",
    "pep_x_intl",
    "sar_history_x_kyc",
    "fund_exit_tier",
    "binary_risk_flag_count",
]


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely converts arbitrary values to float."""
    if val is None:
        return default
    try:
        if isinstance(val, (int, float)):
            return float(val)
        cleaned = str(val).replace(",", "").replace("$", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely converts arbitrary values to int."""
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def calculate_alert_tier(alert_count: float) -> int:
    """
    Tier mapping for alerts:
      0: alert_count == 0
      1: 1 <= alert_count <= 2
      2: 3 <= alert_count <= 5
      3: 6 <= alert_count <= 10
      4: alert_count >= 11
    """
    c = int(round(alert_count))
    if c <= 0:
        return 0
    elif c <= 2:
        return 1
    elif c <= 5:
        return 2
    elif c <= 10:
        return 3
    else:
        return 4


def calculate_kyc_risk_tier(kyc_risk_score: float) -> int:
    """
    Tier mapping for KYC risk:
      0: < 0.40
      1: 0.40 to < 0.70
      2: >= 0.70
    """
    if kyc_risk_score < 0.40:
        return 0
    elif kyc_risk_score < 0.70:
        return 1
    else:
        return 2


def calculate_fund_exit_tier(fund_exit_ratio: float) -> int:
    """
    Tier mapping for Fund Exit Ratio:
      0: < 0.50
      1: 0.50 to < 0.80
      2: 0.80 to < 0.95
      3: >= 0.95
    """
    if fund_exit_ratio < 0.50:
        return 0
    elif fund_exit_ratio < 0.80:
        return 1
    elif fund_exit_ratio < 0.95:
        return 2
    else:
        return 3


def extract_features_from_structured_case(structured_case: Dict[str, Any]) -> pd.DataFrame:
    """
    Extracts the canonical 33 features from a structured_case dictionary
    (produced by the ingestion layer / DataIngestionService).

    Handles both pre-aggregated features and raw entity collections
    (customer, transactions, alerts, accounts).
    """
    # 1. Direct feature pass-through check (if already present in structured_case or raw_data)
    direct_features: Dict[str, float] = {}
    for col in FEATURE_COLUMNS:
        if col in structured_case:
            direct_features[col] = _safe_float(structured_case[col])

    if len(direct_features) == len(FEATURE_COLUMNS):
        return pd.DataFrame([direct_features])[FEATURE_COLUMNS]

    # 2. Extract constituent sections from structured_case safely
    financial = structured_case.get("financial_activity") or {}
    if isinstance(financial, list):
        financial = financial[0] if financial else {}
    if not isinstance(financial, dict):
        financial = {}

    subject = structured_case.get("subject_profile") or structured_case.get("customer") or {}
    if isinstance(subject, list):
        subject = subject[0] if subject else {}
    if not isinstance(subject, dict):
        subject = {}

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

    raw_csvs = structured_case.get("raw_data_store", {}).get("csv_files", {})
    if not isinstance(raw_csvs, dict):
        raw_csvs = {}

    transactions: List[Dict[str, Any]] = (
        financial.get("transactions", [])
        or structured_case.get("transactions", [])
        or []
    )
    if not transactions and raw_csvs:
        for cname, rows in raw_csvs.items():
            if rows and isinstance(rows, list) and isinstance(rows[0], dict):
                keys = [str(k).lower() for k in rows[0].keys()]
                if any("amount" in k for k in keys) and not any("alert" in k for k in keys):
                    transactions = rows
                    break

    # Base raw values
    amounts: List[float] = []
    directions: List[str] = []
    counterparties: set = set()
    incoming_sources: set = set()

    for tx in transactions:
        # Amount extraction
        amt = 0.0
        for k in ["amount", "value", "total", "txn_amount"]:
            if k in tx:
                amt = _safe_float(tx[k])
                break
        amounts.append(amt)

        # Counterparty extraction
        cp = (
            tx.get("counterparty")
            or tx.get("counterparty_id")
            or tx.get("counterparty_name")
            or tx.get("beneficiary")
            or tx.get("sender")
        )
        if cp:
            counterparties.add(str(cp).strip())

        # Direction extraction
        direction = str(tx.get("direction", "")).lower() or str(tx.get("type", "")).lower()
        directions.append(direction)
        if any(d in direction for d in ["in", "credit", "deposit", "inbound"]):
            if cp:
                incoming_sources.add(str(cp).strip())

    txn_count = len(amounts) if amounts else _safe_int(financial.get("transaction_count", 0))
    if amounts:
        total_txn_amount = sum(amounts)
        avg_txn_amount = total_txn_amount / txn_count if txn_count > 0 else 0.0
        std_txn_amount = float(np.std(amounts)) if txn_count > 1 else 0.0
        max_txn_amount = max(amounts) if amounts else 0.0
    else:
        total_txn_amount = _safe_float(
            financial.get("total_volume") or direct_features.get("total_txn_amount")
        )
        avg_txn_amount = total_txn_amount / max(1, txn_count)
        std_txn_amount = _safe_float(direct_features.get("std_txn_amount", avg_txn_amount * 0.2))
        max_txn_amount = _safe_float(direct_features.get("max_txn_amount", avg_txn_amount * 1.5))

    # Account age extraction
    account_age_days = 0.0
    for k in ["account_age_days", "age_days", "customer_age_days"]:
        if k in subject and _safe_float(subject[k]) > 0:
            account_age_days = _safe_float(subject[k])
            break
        if k in case_details and _safe_float(case_details[k]) > 0:
            account_age_days = _safe_float(case_details[k])
            break

    if account_age_days <= 0:
        from datetime import datetime
        for date_key in ["customer_since", "open_date", "incorporation_date", "date_of_birth"]:
            d_val = subject.get(date_key) or case_details.get(date_key)
            if d_val and isinstance(d_val, str):
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"]:
                    try:
                        dt = datetime.strptime(d_val.strip(), fmt)
                        age = (datetime.now() - dt).days
                        if age > 0:
                            account_age_days = float(age)
                            break
                    except Exception:
                        pass
            if account_age_days > 0:
                break

    if account_age_days <= 0:
        account_age_days = _safe_float(direct_features.get("account_age_days", 365.0))
    if account_age_days <= 0:
        account_age_days = 365.0

    # KYC Risk Score (support text labels and numeric values)
    raw_kyc = (
        subject.get("kyc_risk_score")
        or subject.get("risk_rating")
        or subject.get("risk_score")
        or subject.get("kyc_tier")
        or direct_features.get("kyc_risk_score")
    )
    if isinstance(raw_kyc, (int, float)):
        kyc_risk_score = float(raw_kyc)
    elif isinstance(raw_kyc, str):
        rk_lower = raw_kyc.lower()
        if any(w in rk_lower for w in ["crit", "high", "tier_1", "tier 1", "enhanced", "escalated"]):
            kyc_risk_score = 0.85
        elif any(w in rk_lower for w in ["med", "moderate", "tier_2", "tier 2", "standard"]):
            kyc_risk_score = 0.50
        elif any(w in rk_lower for w in ["low", "tier_3", "tier 3"]):
            kyc_risk_score = 0.20
        else:
            kyc_risk_score = _safe_float(raw_kyc, 0.70)
    else:
        kyc_risk_score = 0.70

    # PEP flag
    pep_val = str(subject.get("pep_flag") or subject.get("is_pep") or subject.get("pep_status") or "").lower()
    pep_flag = 1 if any(p in pep_val for p in ["yes", "true", "1", "politically exposed"]) else 0

    # High Risk Jurisdictions check
    HIGH_RISK_JURISDICTIONS = {
        "iran", "north korea", "dprk", "russia", "syria", "myanmar", "burma",
        "cuba", "panama", "cayman", "seychelles", "cyprus", "bvi", "british virgin islands",
        "uae", "united arab emirates", "dubai", "bahamas", "malta", "gibraltar", "turkey"
    }
    high_risk_country_flag = 0
    raw_text = (
        str(case_details.get("notes", ""))
        + " " + str(case_details.get("primary_violation", ""))
        + " " + str(case_details.get("narrative_summary", ""))
        + " " + str(subject.get("registration_jurisdiction", ""))
        + " " + str(subject.get("nationality", ""))
        + " " + str(subject.get("country_of_residence", ""))
    ).lower()

    for tx in transactions:
        for fld in ["counterparty_country", "origin_country", "destination_country", "bank_country"]:
            c_val = str(tx.get(fld, "")).lower()
            if any(hr in c_val for hr in HIGH_RISK_JURISDICTIONS):
                high_risk_country_flag = 1
                break
        if high_risk_country_flag:
            break

    if not high_risk_country_flag:
        if any(hr in raw_text for hr in HIGH_RISK_JURISDICTIONS):
            high_risk_country_flag = 1
        elif _safe_int(subject.get("high_risk_country_flag") or case_details.get("high_risk_country_flag")):
            high_risk_country_flag = 1

    # Historical SAR flag
    historical_sar_flag = 0
    if _safe_int(subject.get("previous_sar_count", 0)) > 0 or _safe_int(subject.get("historical_sar_flag", 0)) > 0:
        historical_sar_flag = 1
    elif _safe_int(case_details.get("historical_sar_flag", 0)) > 0:
        historical_sar_flag = 1
    elif "previous sar" in raw_text or "prior sar" in raw_text:
        historical_sar_flag = 1

    # International counterparty flag
    intl_flag = 0
    for tx in transactions:
        cp_c = str(tx.get("counterparty_country", "")).strip().lower()
        bk_c = str(tx.get("bank_country", "")).strip().lower()
        if (cp_c and bk_c and cp_c != bk_c) or "swift" in str(tx.get("txn_type", "")).lower() or tx.get("swift_message_type"):
            intl_flag = 1
            break
    if not intl_flag:
        intl_flag = _safe_int(
            financial.get("international_counterparty_flag")
            or direct_features.get("international_counterparty_flag", 0)
        )

    # Alert counts
    alert_ids = case_details.get("alert_ids") or []
    if isinstance(alert_ids, list):
        alert_count_from_ids = float(len(alert_ids))
    else:
        alert_count_from_ids = 0.0

    alert_count = float(
        case_details.get("alert_count")
        or alert_count_from_ids
        or len(supporting.get("records", []))
        or len(raw_csvs.get("transaction_alerts.csv", []))
        or direct_features.get("alert_count", 5.0)
    )
    if alert_count <= 0:
        alert_count = 5.0

    # Ratios and behavioral metrics
    fund_exit_ratio = _safe_float(
        financial.get("fund_exit_ratio")
        or direct_features.get("fund_exit_ratio", 0.75)
    )
    burst_score = _safe_float(
        financial.get("burst_score")
        or direct_features.get("burst_score", 0.60)
    )
    time_to_first_outbound_minutes = _safe_float(
        financial.get("time_to_first_outbound_minutes")
        or direct_features.get("time_to_first_outbound_minutes", 120.0)
    )
    txn_velocity = _safe_float(
        financial.get("txn_velocity")
        or direct_features.get("txn_velocity", 5.0)
    )
    distinct_cp_count = len(counterparties) if counterparties else _safe_int(
        direct_features.get("distinct_counterparties", 10)
    )
    incoming_sources_count = len(incoming_sources) if incoming_sources else _safe_int(
        direct_features.get("incoming_sources_count", 6)
    )
    diversity_score = _safe_float(
        direct_features.get("counterparty_diversity_score", 0.45)
    )

    # 3. Compute 33 canonical features
    features: Dict[str, float] = {}

    # Group A (7)
    features["total_txn_amount_cbrt"] = float(np.cbrt(max(0.0, total_txn_amount)))
    features["avg_txn_amount_cbrt"] = float(np.cbrt(max(0.0, avg_txn_amount)))
    features["std_txn_amount_cbrt"] = float(np.cbrt(max(0.0, std_txn_amount)))
    features["txn_count_log"] = float(np.log(txn_count)) if txn_count > 0 else 0.0
    features["txn_amount_cv"] = float(std_txn_amount / avg_txn_amount) if avg_txn_amount > 0 else 0.0
    features["max_to_avg_txn_ratio"] = float(max_txn_amount / avg_txn_amount) if avg_txn_amount > 0 else 1.0
    features["fund_exit_ratio"] = float(np.clip(fund_exit_ratio, 0.0, 1.0))

    # Group B (4)
    features["burst_score"] = float(np.clip(burst_score, 0.0, 1.0))
    features["time_to_first_outbound_minutes_log"] = (
        float(np.log(time_to_first_outbound_minutes)) if time_to_first_outbound_minutes > 0 else 0.0
    )
    features["txn_velocity_log"] = float(np.log(txn_velocity)) if txn_velocity > 0 else 0.0
    features["burst_per_age"] = (
        float(burst_score / np.log(account_age_days + 1.0)) if account_age_days > 0 else 0.0
    )

    # Group C (5)
    features["distinct_counterparties_log"] = (
        float(np.log(distinct_cp_count)) if distinct_cp_count > 0 else 0.0
    )
    features["incoming_sources_count_log"] = (
        float(np.log(incoming_sources_count)) if incoming_sources_count > 0 else 0.0
    )
    features["counterparty_diversity_score"] = float(np.clip(diversity_score, 0.0, 1.0))
    features["counterparty_to_txn_ratio"] = (
        float(distinct_cp_count / txn_count) if txn_count > 0 else 1.0
    )
    inc_count = incoming_sources_count
    out_count = max(1, distinct_cp_count - inc_count)
    features["incoming_to_outgoing_ratio"] = float(inc_count / out_count)

    # Group D (4)
    features["alert_count"] = float(alert_count)
    features["alert_density"] = float(alert_count / max(1.0, txn_count))
    features["alert_tier"] = float(calculate_alert_tier(alert_count))
    features["kyc_x_alert"] = float(kyc_risk_score * np.log(alert_count + 1.0))

    # Group E (7)
    features["international_counterparty_flag"] = float(intl_flag)
    features["high_risk_country_flag"] = float(high_risk_country_flag)
    features["pep_flag"] = float(pep_flag)
    features["kyc_risk_score"] = float(np.clip(kyc_risk_score, 0.0, 1.0))
    features["kyc_risk_tier"] = float(calculate_kyc_risk_tier(kyc_risk_score))
    features["historical_sar_flag"] = float(historical_sar_flag)

    # Binary flags summary
    binary_count = (
        int(pep_flag)
        + int(high_risk_country_flag)
        + int(intl_flag)
        + int(historical_sar_flag)
    )
    high_risk_comb = 1 if (
        pep_flag == 1
        or high_risk_country_flag == 1
        or historical_sar_flag == 1
        or binary_count >= 2
        or (features["kyc_risk_tier"] >= 2 and features["alert_tier"] >= 2)
    ) else 0
    features["high_risk_combined"] = float(high_risk_comb)

    # Group F (6)
    features["burst_x_exit"] = float(features["burst_score"] * features["fund_exit_ratio"])
    features["hr_country_x_exit"] = float(features["high_risk_country_flag"] * features["fund_exit_ratio"])
    features["pep_x_intl"] = float(features["pep_flag"] * features["international_counterparty_flag"])
    features["sar_history_x_kyc"] = float(features["historical_sar_flag"] * features["kyc_risk_score"])
    features["fund_exit_tier"] = float(calculate_fund_exit_tier(features["fund_exit_ratio"]))
    features["binary_risk_flag_count"] = float(binary_count)

    # Ensure all 33 columns are present in exact order
    row_df = pd.DataFrame([features])[FEATURE_COLUMNS]
    return row_df


def extract_features_from_csv(csv_path: str, row_index: int = 0) -> pd.DataFrame:
    """
    Reads a local CSV (e.g. data_engineered.csv or transaction export)
    and formats/computes the 33 features.
    """
    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError(f"CSV at {csv_path} is empty.")

    # If the CSV already has all 33 engineered columns (like data_engineered.csv)
    if all(col in df.columns for col in FEATURE_COLUMNS):
        selected_row = df[FEATURE_COLUMNS].iloc[[row_index]].copy()
        return selected_row.astype(float)

    # Otherwise, convert the row into a structured_case dict and process
    row_dict = df.iloc[row_index].to_dict()
    return extract_features_from_structured_case(row_dict)
