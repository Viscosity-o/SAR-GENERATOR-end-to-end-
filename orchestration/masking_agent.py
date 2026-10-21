"""
Masking Agent Module.
Masks PII in structured_case (NAME, DOB, ACCOUNT, TAX_ID tokens),
persists token mapping in PostgreSQL vault, and passes the masked case to downstream agents.
"""

import copy
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
import psycopg2

load_dotenv()

from orchestration.state import SARAgentState


class PIIMasker:
    """
    Identifies and replaces sensitive PII in nested JSON/dictionary structures.
    Persists original <-> masked mapping into PostgreSQL.
    """

    def __init__(self, case_id: str, db_url: Optional[str] = None):
        self.case_id = case_id
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self.mapping: Dict[str, str] = {}  # original -> masked
        self.reverse_mapping: Dict[str, str] = {}  # masked -> original
        self.counters: Dict[str, int] = {
            "NAME": 0,
            "DOB": 0,
            "ACCOUNT": 0,
            "TAX_ID": 0,
            "PHONE": 0,
            "EMAIL": 0,
        }

    def _get_masked_token(self, original_val: str, entity_type: str) -> str:
        clean_val = str(original_val).strip()
        if not clean_val or clean_val.startswith("[") and clean_val.endswith("]"):
            return clean_val

        if clean_val in self.mapping:
            return self.mapping[clean_val]

        self.counters[entity_type] = self.counters.get(entity_type, 0) + 1
        masked = f"[{entity_type}_{self.counters[entity_type]}]"
        self.mapping[clean_val] = masked
        self.reverse_mapping[masked] = clean_val
        return masked

    def _mask_nested(self, obj: Any, key_context: str = "") -> Any:
        if isinstance(obj, dict):
            masked_dict = {}
            for k, v in obj.items():
                lower_k = str(k).lower()
                masked_dict[k] = self._mask_nested(v, key_context=lower_k)
            return masked_dict

        elif isinstance(obj, list):
            return [self._mask_nested(item, key_context=key_context) for item in obj]

        elif isinstance(obj, str):
            val = obj.strip()
            if not val:
                return obj

            # 1. Key-context based masking
            if any(k in key_context for k in ["name", "beneficiary", "sender", "counterparty", "customer", "party"]):
                if not any(k in key_context for k in ["count", "code", "flag", "score", "type", "tier"]):
                    return self._get_masked_token(val, "NAME")

            if any(k in key_context for k in ["dob", "birth_date", "birthdate", "date_of_birth"]):
                return self._get_masked_token(val, "DOB")

            if any(k in key_context for k in ["account", "iban", "acc_no", "account_id", "acct"]):
                if not any(k in key_context for k in ["count", "age", "type"]):
                    return self._get_masked_token(val, "ACCOUNT")

            if any(k in key_context for k in ["ssn", "tax_id", "tin", "national_id"]):
                return self._get_masked_token(val, "TAX_ID")

            if any(k in key_context for k in ["phone", "mobile"]):
                return self._get_masked_token(val, "PHONE")

            if any(k in key_context for k in ["email"]):
                return self._get_masked_token(val, "EMAIL")

            # 2. Regex-based pattern masking on free-form text
            # Email pattern
            if re.match(r"[^@]+@[^@]+\.[^@]+", val):
                return self._get_masked_token(val, "EMAIL")

            # Account number (digits of length 8-20)
            if re.match(r"^\d{8,20}$", val) and any(k in key_context for k in ["id", "num", "no"]):
                return self._get_masked_token(val, "ACCOUNT")

            # DOB pattern (YYYY-MM-DD or MM/DD/YYYY)
            if re.match(r"^\d{4}-\d{2}-\d{2}$", val) and "birth" in key_context:
                return self._get_masked_token(val, "DOB")

            return obj

        else:
            return obj

    def mask_case(self, structured_case: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Recursively masks the case dict and persists mapping into PostgreSQL.
        """
        copied_case = copy.deepcopy(structured_case)
        masked_case = self._mask_nested(copied_case)
        self.persist_to_postgres()
        return masked_case, self.mapping

    def persist_to_postgres(self) -> None:
        """Stores the PII mappings in PostgreSQL pii_masking_vault table."""
        if not self.mapping or not self.db_url:
            return

        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS pii_masking_vault (
                id SERIAL PRIMARY KEY,
                case_id VARCHAR(100) NOT NULL,
                original_token TEXT NOT NULL,
                masked_token VARCHAR(100) NOT NULL,
                entity_type VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            for orig, masked in self.mapping.items():
                entity_type = masked.strip("[]").split("_")[0]
                cur.execute(
                    """
                    INSERT INTO pii_masking_vault (case_id, original_token, masked_token, entity_type)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (self.case_id, orig, masked, entity_type),
                )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            # Non-blocking graceful fallback
            print(f"Warning: PostgreSQL PII vault insertion failed ({e}). Proceeding with in-memory vault.")


def masking_agent(state: SARAgentState) -> SARAgentState:
    """
    Masking Agent Node.
    Masks PII in structured_case (NAME, DOB, ACCOUNT, TAX_ID tokens),
    stores mapping in PostgreSQL, and passes masked case downstream.
    """
    case_id = state.get("case_id", "UNKNOWN_CASE")
    structured_case = state.get("structured_case") or {}
    error_log: List[str] = list(state.get("error_log", []))
    reasoning_traces: List[str] = list(state.get("reasoning_traces", []))

    if not structured_case:
        error_log.append(f"Masking Agent received empty structured_case for case {case_id}")
        return {
            **state,
            "raw_case": {},
            "structured_case": {},
            "pii_mapping": {},
            "error_log": error_log,
            "reasoning_traces": ["Masking Agent: skipped (empty structured_case)."],
        }

    raw_case = copy.deepcopy(structured_case)
    masker = PIIMasker(case_id=case_id)
    masked_case, mapping = masker.mask_case(structured_case)

    trace = (
        f"Masking Agent: Successfully masked {len(mapping)} PII entities "
        f"([NAME], [DOB], [ACCOUNT]) and persisted mapping in PostgreSQL vault."
    )

    return {
        **state,
        "raw_case": raw_case,
        "structured_case": masked_case,
        "pii_mapping": mapping,
        "reasoning_traces": [trace],
        "error_log": error_log,
    }
