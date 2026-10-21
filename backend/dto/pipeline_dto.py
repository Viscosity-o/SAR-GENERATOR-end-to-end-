"""
DTO Schemas for the 2-call SAR Generation Microservice.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IngestCall1Request(BaseModel):
    """Payload for Call 1 (/ingest)."""
    case_id: str = Field(..., description="Unique case identifier, e.g. CASE-2026-001")
    s3_bucket: Optional[str] = Field(default="", description="Storage bucket name if using storage")
    s3_prefix: Optional[str] = Field(default="", description="Storage folder prefix")
    transactions_csv: Optional[str] = Field(default="", description="Local CSV fallback file path")
    structured_case: Optional[Dict[str, Any]] = Field(default=None, description="Pre-loaded ingestion case dictionary")


class IngestCall1Response(BaseModel):
    """Response returned by Call 1 (/ingest)."""
    status: str = "success"
    case_id: str
    sar_worthy: bool
    typology: str
    confidence_score: float
    risk_score: float
    structured_case: Optional[Dict[str, Any]] = None
    error_log: List[str] = []


class AnalyseCall2Request(BaseModel):
    """Payload for Call 2 (/analyse)."""
    case_id: str = Field(..., description="Case identifier")
    structured_case: Dict[str, Any] = Field(..., description="Full structured case dictionary")
    typology: Optional[str] = Field(default="Structuring", description="Typology from Call 1")
    risk_score: Optional[float] = Field(default=0.75, description="Risk score from Call 1")
    confidence_score: Optional[float] = Field(default=0.90, description="Confidence score from Call 1")
    sar_worthy: Optional[bool] = Field(default=True, description="SAR-worthy flag from Call 1")


class AnalyseCall2Response(BaseModel):
    """Response returned by Call 2 (/analyse)."""
    status: str = "success"
    case_id: str
    sar_draft: Dict[str, Any]
    compliance_passed: bool
    quality_score: float
    compliance_issues: List[str] = []
    plan: Dict[str, Any]
    triggered_rules: List[Dict[str, Any]] = []
    quantified_indicators: Dict[str, Any] = {}
    cognitive_event_flow: Dict[str, Any] = {}
    revision_count: int = 1
    reasoning_traces: List[str] = []
