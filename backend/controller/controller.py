import os
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from supabase import Client, create_client

# Load environment variables from .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "uploads")

router = APIRouter(prefix="/api/files", tags=["File Controller"])


def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY or "your-project-id" in SUPABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase credentials not configured. Please set SUPABASE_URL and SUPABASE_KEY in .env",
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def validate_file_extension(file: UploadFile, expected_ext: str, field_name: str) -> None:
    """Validate that the uploaded file has the expected extension."""
    filename = file.filename or ""
    if not filename.lower().endswith(f".{expected_ext.lower()}"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Field '{field_name}' must be a .{expected_ext} file. Received: '{filename}'",
        )


@router.post("/upload")
async def upload_files_to_bucket(
    json_file_1: UploadFile = File(..., description="First JSON file"),
    json_file_2: UploadFile = File(..., description="Second JSON file"),
    csv_file_1: UploadFile = File(..., description="First CSV file"),
    csv_file_2: UploadFile = File(..., description="Second CSV file"),
    folder_name: str = Form(default="data", description="Subfolder path inside the Supabase bucket"),
) -> Dict[str, Any]:
    """
    Receives 2 JSON files and 2 CSV files from the frontend
    and uploads them to the specified Supabase storage bucket folder.
    """
    # 1. Validate file extensions
    validate_file_extension(json_file_1, "json", "json_file_1")
    validate_file_extension(json_file_2, "json", "json_file_2")
    validate_file_extension(csv_file_1, "csv", "csv_file_1")
    validate_file_extension(csv_file_2, "csv", "csv_file_2")

    # 2. Get Supabase client
    supabase = get_supabase_client()

    # 3. Prepare files mapping
    files_to_upload = [
        ("json_file_1", json_file_1, "application/json"),
        ("json_file_2", json_file_2, "application/json"),
        ("csv_file_1", csv_file_1, "text/csv"),
        ("csv_file_2", csv_file_2, "text/csv"),
    ]

    clean_folder = folder_name.strip("/")
    upload_results: List[Dict[str, Any]] = []

    # 4. Upload each file to Supabase storage bucket
    for field_name, upload_file, content_type in files_to_upload:
        try:
            file_bytes = await upload_file.read()
            file_path = f"{clean_folder}/{upload_file.filename}" if clean_folder else upload_file.filename

            # Upload to Supabase bucket with upsert enabled
            supabase.storage.from_(SUPABASE_BUCKET).upload(
                path=file_path,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"},
            )

            # Retrieve public URL for confirmation
            public_url_response = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(file_path)

            upload_results.append({
                "field": field_name,
                "filename": upload_file.filename,
                "path": file_path,
                "content_type": content_type,
                "size_bytes": len(file_bytes),
                "url": public_url_response,
                "status": "success",
            })
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload '{upload_file.filename}' to Supabase bucket '{SUPABASE_BUCKET}': {str(e)}",
            )

    return {
        "message": "All 4 files (2 JSON, 2 CSV) successfully uploaded to Supabase storage.",
        "bucket": SUPABASE_BUCKET,
        "folder": clean_folder,
        "uploaded_files": upload_results,
    }
