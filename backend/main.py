import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

try:
    from backend.controller import upload_router, ingestion_router, pipeline_router
except ImportError:
    from controller import upload_router, ingestion_router, pipeline_router

app = FastAPI(
    title=os.getenv("APP_NAME", "SAR System Backend"),
    description="FastAPI Backend with File Upload, Data Ingestion, and 6-Agent LangGraph Pipeline",
    version="1.0.0",
)

# CORS setup for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount controller routers
app.include_router(upload_router)
app.include_router(ingestion_router)
app.include_router(pipeline_router)


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "SAR System Data Ingestion Backend",
        "endpoints": {
            "upload_files": "/api/files/upload",
            "ingest_case": "/api/ingestion/case/{case_id}",
            "ingest_custom": "/api/ingestion/ingest",
            "docs": "/docs",
        },
    }
