"""
Pipeline Controller exposing the 2-call microservice:
  1. POST /ingest (Call 1) -> {sar_worthy, typology, confidence_score, risk_score}
  2. POST /analyse (Call 2) -> {sar_draft, compliance_passed, quality_score, plan, triggered_rules}
"""

from fastapi import APIRouter, HTTPException, status
from backend.dto.pipeline_dto import (
    IngestCall1Request,
    IngestCall1Response,
    AnalyseCall2Request,
    AnalyseCall2Response,
)
from orchestration.pipeline import run_call_1_ingest, run_call_2_analyse

router = APIRouter(prefix="", tags=["SAR 6-Agent Pipeline Microservice"])


@router.post(
    "/ingest",
    response_model=IngestCall1Response,
    summary="Call 1: Ingestion & ML Classification (Agent 1)",
    description="Loads case data, extracts 33 features, and executes pre-trained XGBoost classification.",
)
@router.post(
    "/api/ingest",
    response_model=IngestCall1Response,
    include_in_schema=False,
)
@router.post(
    "/api/pipeline/ingest",
    response_model=IngestCall1Response,
    include_in_schema=False,
)
async def ingest_endpoint(request: IngestCall1Request):
    try:
        result = run_call_1_ingest(
            case_id=request.case_id,
            s3_bucket=request.s3_bucket or "",
            s3_prefix=request.s3_prefix or "",
            transactions_csv=request.transactions_csv or "",
            structured_case=request.structured_case,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Call 1 Ingestion failed: {str(e)}",
        )


@router.post(
    "/analyse",
    response_model=AnalyseCall2Response,
    summary="Call 2: Multi-Agent Analysis & SAR Generation",
    description="Runs Masking Agent -> Agent 2 (Planner) -> Agent 3 (Evidence) -> Agent 5 (Narrative) -> Agent 6 (Compliance loop).",
)
@router.post(
    "/api/analyse",
    response_model=AnalyseCall2Response,
    include_in_schema=False,
)
@router.post(
    "/api/pipeline/analyse",
    response_model=AnalyseCall2Response,
    include_in_schema=False,
)
async def analyse_endpoint(request: AnalyseCall2Request):

    try:
        result = run_call_2_analyse(
            case_id=request.case_id,
            structured_case=request.structured_case,
            typology=request.typology or "Structuring",
            risk_score=request.risk_score or 0.75,
            confidence_score=request.confidence_score or 0.90,
            sar_worthy=request.sar_worthy if request.sar_worthy is not None else True,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Call 2 Analysis failed: {str(e)}",
        )
