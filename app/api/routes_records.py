from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import AnalysisRecordResponse
from app.services.storage_service import load_analysis_record

router = APIRouter(tags=["records"])


@router.get("/records/{record_id}", response_model=AnalysisRecordResponse)
def get_record(record_id: int) -> AnalysisRecordResponse:
    record = load_analysis_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="record not found")
    return AnalysisRecordResponse.model_validate(record)
