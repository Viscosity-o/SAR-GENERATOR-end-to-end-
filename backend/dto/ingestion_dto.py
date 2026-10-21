from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    """Request payload for case data ingestion."""
    case_id: str = Field(..., description="Unique Case ID or folder name in Supabase storage")
    bucket_name: Optional[str] = Field(None, description="Optional Supabase bucket name (defaults to SUPABASE_BUCKET in .env)")
    file_names: Optional[List[str]] = Field(None, description="Optional list of exact 4 file names to download")


class FileMetadataDTO(BaseModel):
    """Metadata for an ingested file."""
    filename: str
    file_type: str
    size_bytes: int
    record_count: Optional[int] = None


class IngestionMetadataDTO(BaseModel):
    """Metadata about the ingestion run."""
    ingested_at: str
    source_storage: str
    bucket: str
    folder: str
    total_files: int
    files: List[FileMetadataDTO]


class StructuredCaseResponse(BaseModel):
    """Response DTO containing the complete structured SAR case."""
    status: str
    case_id: str
    structured_case: Dict[str, Any]
