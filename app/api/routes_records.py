from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import AnalysisRecordResponse, AnalysisRecordSummary
from app.services.storage_service import list_saved_analysis_records, load_analysis_record

router = APIRouter(tags=["records"])


@router.get("/records", response_model=list[AnalysisRecordSummary])
def list_records(limit: int = 20, keyword: str | None = None) -> list[AnalysisRecordSummary]:
    records = list_saved_analysis_records(limit=limit, keyword=keyword)
    return [AnalysisRecordSummary.model_validate(record) for record in records]


@router.get("/records/{record_id}", response_model=AnalysisRecordResponse)
def get_record(record_id: int) -> AnalysisRecordResponse:
    record = load_analysis_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="record not found")
    return AnalysisRecordResponse.model_validate(record)
