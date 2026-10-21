import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from supabase import Client, create_client

# Load environment configuration
load_dotenv()


class DataIngestionService:
    """
    Data Ingestion Service for SAR (Suspicious Activity Report) systems.
    Executes sequentially:
    1. Download 4 input files for a case from Supabase Storage (S3-compatible API, NOT AWS).
    2. Parse them (JSON and CSV).
    3. Build a structured_case dict.
    """

    def __init__(self, bucket_name: Optional[str] = None):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.default_bucket = bucket_name or os.getenv("SUPABASE_BUCKET", "Uploads")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "Supabase credentials missing. Ensure SUPABASE_URL and SUPABASE_KEY are set in .env"
            )

        # Initialize Supabase Client (connects to Supabase S3-compatible storage API)
        self.client: Client = create_client(self.supabase_url, self.supabase_key)

    # -------------------------------------------------------------------------
    # STEP 1: Download 4 input files from Supabase Storage
    # -------------------------------------------------------------------------
    def download_case_files(
        self,
        case_id: str,
        bucket_name: Optional[str] = None,
        file_names: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, bytes], Dict[str, Any]]:
        """
        Step 1: Download 4 input files for a case from Supabase Storage.
        Returns:
            - downloaded_files: Dict[filename, file_bytes]
            - metadata: Dict containing storage and file metadata
        """
        bucket = bucket_name or self.default_bucket
        clean_folder = case_id.strip("/")
        downloaded_files: Dict[str, bytes] = {}
        files_metadata: List[Dict[str, Any]] = []

        # Determine target file paths to download
        target_files: List[str] = []

        if file_names and len(file_names) > 0:
            target_files = file_names
        else:
            # Auto-discover files in case folder
            try:
                storage_items = self.client.storage.from_(bucket).list(clean_folder)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to query Supabase storage bucket '{bucket}' at folder '{clean_folder}': {str(e)}"
                )

            # Filter out folder placeholders and hidden system files
            for item in storage_items:
                name = item.get("name", "")
                if name and not name.startswith(".") and name != ".emptyFolderPlaceholder":
                    target_files.append(name)

        if not target_files:
            raise FileNotFoundError(
                f"No files found for case '{case_id}' in Supabase bucket '{bucket}'. Expected 4 input files."
            )

        if len(target_files) != 4:
            raise ValueError(
                f"Case '{case_id}' must contain exactly 4 input files. Found {len(target_files)}: {target_files}"
            )

        # Download each of the 4 files
        for filename in target_files:
            file_key = f"{clean_folder}/{filename}" if clean_folder and not filename.startswith(f"{clean_folder}/") else filename

            try:
                file_bytes = self.client.storage.from_(bucket).download(file_key)
            except Exception as e:
                raise RuntimeError(
                    f"Failed downloading '{file_key}' from Supabase bucket '{bucket}': {str(e)}"
                )

            base_name = os.path.basename(filename)
            downloaded_files[base_name] = file_bytes

            files_metadata.append({
                "filename": base_name,
                "storage_path": file_key,
                "size_bytes": len(file_bytes),
                "extension": os.path.splitext(base_name)[1].lower().lstrip("."),
            })

        ingestion_meta = {
            "bucket": bucket,
            "folder": clean_folder,
            "files": files_metadata,
            "total_files": len(downloaded_files),
        }

        return downloaded_files, ingestion_meta

    # -------------------------------------------------------------------------
    # STEP 2: Parse them (JSON and CSV)
    # -------------------------------------------------------------------------
    def parse_files(self, downloaded_files: Dict[str, bytes]) -> Dict[str, Any]:
        """
        Step 2: Parse downloaded raw bytes into structured Python data structures.
        Supports .json and .csv files.
        """
        parsed_data: Dict[str, Any] = {}

        for filename, raw_bytes in downloaded_files.items():
            ext = os.path.splitext(filename)[1].lower()

            # Decode text content safely
            try:
                text_content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text_content = raw_bytes.decode("latin-1")

            if ext == ".json":
                try:
                    parsed_json = json.loads(text_content) if text_content.strip() else {}
                    parsed_data[filename] = {
                        "type": "json",
                        "content": parsed_json,
                    }
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON format in file '{filename}': {str(e)}")

            elif ext == ".csv":
                try:
                    csv_file = io.StringIO(text_content)
                    reader = csv.DictReader(csv_file)
                    records = [row for row in reader]

                    parsed_data[filename] = {
                        "type": "csv",
                        "row_count": len(records),
                        "columns": reader.fieldnames or [],
                        "records": records,
                    }
                except Exception as e:
                    raise ValueError(f"Failed parsing CSV in file '{filename}': {str(e)}")

            else:
                # Fallback for unrecognized extension
                parsed_data[filename] = {
                    "type": "raw",
                    "content": text_content,
                }

        return parsed_data

    # -------------------------------------------------------------------------
    # STEP 3: Build a structured_case dict
    # -------------------------------------------------------------------------
    def build_structured_case(
        self,
        case_id: str,
        parsed_files: Dict[str, Any],
        storage_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Step 3: Transform parsed files into a unified canonical structured_case dict
        tailored for Suspicious Activity Report (SAR) analysis and investigation.
        """
        json_files: Dict[str, Any] = {}
        csv_files: Dict[str, Any] = {}

        for fname, data in parsed_files.items():
            if data["type"] == "json":
                json_files[fname] = data["content"]
            elif data["type"] == "csv":
                csv_files[fname] = data["records"]

        # 1. Identify Case Details and Subject Profile from JSON files
        case_details: Dict[str, Any] = {}
        subject_profile: Dict[str, Any] = {}
        other_json: Dict[str, Any] = {}

        for fname, content in json_files.items():
            lower_name = fname.lower()
            if any(k in lower_name for k in ["case", "alert", "metadata", "sar", "report"]):
                case_details = content
            elif any(k in lower_name for k in ["subject", "customer", "party", "entity", "profile"]):
                subject_profile = content
            else:
                other_json[fname] = content

        # If heuristics didn't match, distribute into slots
        if not case_details and json_files:
            first_key = list(json_files.keys())[0]
        # Normalize subject_profile if list (e.g., customer_kyc.json array)
        if isinstance(subject_profile, list):
            subject_profile_list = subject_profile
            subject_profile = subject_profile[0] if len(subject_profile) > 0 else {}
        else:
            subject_profile_list = [subject_profile] if subject_profile else []

        if isinstance(case_details, list):
            case_details = case_details[0] if len(case_details) > 0 else {}

        # 2. Identify Transactions and Supporting Accounts/Activities from CSV files
        transactions: List[Dict[str, Any]] = []
        supporting_records: List[Dict[str, Any]] = []
        other_csv: Dict[str, Any] = {}

        for fname, rows in csv_files.items():
            lower_name = fname.lower()
            sample_row = rows[0] if rows and isinstance(rows[0], dict) else {}
            sample_keys = [str(k).lower() for k in sample_row.keys()]

            is_alert = (
                any("alert" in k for k in sample_keys)
                or any("rule" in k for k in sample_keys)
                or any(k in lower_name for k in ["alert", "supporting", "audit"])
            )
            is_tx = (
                not is_alert
                and (
                    any(k in sample_keys for k in ["amount", "txn_id", "direction", "counterparty"])
                    or any(k in lower_name for k in ["transaction", "tx", "trans", "payment"])
                )
            )

            if is_alert:
                supporting_records = rows
            elif is_tx:
                transactions = rows
            elif any(k in lower_name for k in ["account", "balance", "log"]):
                supporting_records = rows
            else:
                other_csv[fname] = rows

        # If heuristics didn't match, distribute into slots
        if not transactions and csv_files:
            for k, rows in csv_files.items():
                if rows is not supporting_records:
                    transactions = rows
                    break
        if not supporting_records and len(csv_files) > 1:
            for k, rows in csv_files.items():
                if rows is not transactions:
                    supporting_records = rows
                    break

        # 3. Compute SAR financial and summary metrics
        total_tx_amount = 0.0
        currencies = set()
        for tx in transactions:
            for key, val in tx.items():
                if any(amt_k in key.lower() for amt_k in ["amount", "value", "total"]):
                    try:
                        total_tx_amount += float(str(val).replace(",", "").replace("$", ""))
                    except (ValueError, TypeError):
                        pass
                if any(curr_k in key.lower() for curr_k in ["currency", "curr"]):
                    if val:
                        currencies.add(str(val).strip().upper())

        # Build canonical structured_case dict
        structured_case: Dict[str, Any] = {
            "case_id": case_id,
            "sar_system_version": "1.0",
            "ingestion_metadata": {
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "source": "supabase_storage_s3_compatible",
                "bucket": storage_meta.get("bucket"),
                "folder": storage_meta.get("folder"),
                "total_files_ingested": len(parsed_files),
                "file_manifest": storage_meta.get("files", []),
            },
            "case_details": case_details,
            "subject_profile": subject_profile,
            "financial_activity": {
                "transaction_count": len(transactions),
                "total_volume": round(total_tx_amount, 2),
                "currencies_detected": sorted(list(currencies)),
                "transactions": transactions,
            },
            "supporting_activity": {
                "record_count": len(supporting_records),
                "records": supporting_records,
            },
            "raw_data_store": {
                "json_files": json_files,
                "csv_files": csv_files,
                "other_files": {**other_json, **other_csv},
            },
            "investigation_readiness": {
                "has_case_details": bool(case_details),
                "has_subject_profile": bool(subject_profile),
                "has_transaction_history": bool(transactions),
                "has_supporting_data": bool(supporting_records),
                "ready_for_rag_pipeline": True,
            },
        }

        return structured_case

    # -------------------------------------------------------------------------
    # Main Ingestion Orchestrator: 1 -> 2 -> 3
    # -------------------------------------------------------------------------
    def ingest_case(
        self,
        case_id: str,
        bucket_name: Optional[str] = None,
        file_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrates full ingestion in sequence:
        1. Download 4 input files
        2. Parse them
        3. Build structured_case dict
        """
        # Step 1: Download
        downloaded_files, storage_meta = self.download_case_files(
            case_id=case_id,
            bucket_name=bucket_name,
            file_names=file_names,
        )

        # Step 2: Parse
        parsed_files = self.parse_files(downloaded_files)

        # Step 3: Build structured_case
        structured_case = self.build_structured_case(
            case_id=case_id,
            parsed_files=parsed_files,
            storage_meta=storage_meta,
        )

        return structured_case
