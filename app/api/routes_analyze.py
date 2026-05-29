from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import FullAnalysisRequest
from app.schemas.report import FinalReport
from app.services.mock_pipeline import run_mock_pipeline

router = APIRouter(tags=["analyze"])


@router.post("/analyze/full", response_model=FinalReport)
def analyze_full(request: FullAnalysisRequest) -> FinalReport:
    try:
        return run_mock_pipeline(
            resume_text=request.resume_text,
            jd_text=request.jd_text,
            use_llm_jd=request.use_llm_jd,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
