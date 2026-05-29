from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.jd_analysis_agent import analyze_jd
from app.schemas.api import JDAnalysisRequest
from app.schemas.job import JobAnalysis

router = APIRouter(tags=["jobs"])


@router.post("/jobs/analyze", response_model=JobAnalysis)
def analyze_job(request: JDAnalysisRequest) -> JobAnalysis:
    try:
        return analyze_jd(request.jd_text, use_llm=request.use_llm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
