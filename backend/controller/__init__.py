from .controller import router as upload_router
from .ingestion_controller import router as ingestion_router
from .pipeline_controller import router as pipeline_router

# Backward compatibility: router points to upload_router
router = upload_router

__all__ = ["upload_router", "ingestion_router", "pipeline_router", "router"]

