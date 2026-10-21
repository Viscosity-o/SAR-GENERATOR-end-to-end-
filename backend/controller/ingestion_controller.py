from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Path, Query, status

try:
    from backend.dto.ingestion_dto import IngestionRequest, StructuredCaseResponse
    from backend.services.ingestion_service import DataIngestionService
except ImportError:
    from dto.ingestion_dto import IngestionRequest, StructuredCaseResponse
    from services.ingestion_service import DataIngestionService

router = APIRouter(prefix="/api/ingestion", tags=["Data Ingestion Service"])


@router.post(
    "/case/{case_id}",
    response_model=StructuredCaseResponse,
    summary="Ingest a SAR case from Supabase Storage",
    description="Downloads 4 input files (JSON/CSV) for the specified case, parses them, and builds a structured_case dict.",
)
async def ingest_case_by_id(
    case_id: str = Path(..., description="The SAR case identifier / folder name in Supabase storage"),
    bucket_name: Optional[str] = Query(None, description="Optional override for Supabase storage bucket"),
) -> Dict[str, Any]:
    """
    Ingest a SAR case by its case_id:
    1. Downloads 4 input files from Supabase Storage.
    2. Parses the JSON and CSV contents.
    3. Builds and returns the structured_case dict.
    """
    try:
        service = DataIngestionService(bucket_name=bucket_name)
        structured_case = service.ingest_case(case_id=case_id, bucket_name=bucket_name)
        return {
            "status": "success",
            "case_id": case_id,
            "structured_case": structured_case,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data ingestion failed: {str(e)}",
        )


@router.post(
    "/ingest",
    response_model=StructuredCaseResponse,
    summary="Ingest a SAR case with custom options",
    description="Allows custom bucket names or explicit 4-file manifests for ingestion.",
)
async def ingest_case_custom(request: IngestionRequest) -> Dict[str, Any]:
    """Ingest a case using a JSON payload with custom parameters."""
    try:
        service = DataIngestionService(bucket_name=request.bucket_name)
        structured_case = service.ingest_case(
            case_id=request.case_id,
            bucket_name=request.bucket_name,
            file_names=request.file_names,
        )
        return {
            "status": "success",
            "case_id": request.case_id,
            "structured_case": structured_case,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data ingestion failed: {str(e)}",
        )
