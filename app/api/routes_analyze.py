from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import FullAnalysisRequest, FullAnalysisResponse
from app.services.storage_service import save_final_report
from app.services.mock_pipeline import run_mock_pipeline

router = APIRouter(tags=["analyze"])


@router.post("/analyze/full", response_model=FullAnalysisResponse)
def analyze_full(request: FullAnalysisRequest) -> FullAnalysisResponse:
    try:
        result = run_mock_pipeline(
            resume_text=request.resume_text,
            jd_text=request.jd_text,
            use_llm_jd=request.use_llm_jd,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_id = save_final_report(result) if request.save_result else None
    return FullAnalysisResponse(
        **result.model_dump(),
        record_id=record_id,
    )
