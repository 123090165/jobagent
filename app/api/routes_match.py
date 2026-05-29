from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import MatchAnalysisRequest
from app.schemas.match import MatchReport
from app.services.mock_pipeline import mock_match_analysis

router = APIRouter(tags=["match"])


@router.post("/match/analyze", response_model=MatchReport)
def analyze_match(request: MatchAnalysisRequest) -> MatchReport:
    return mock_match_analysis(
        resume_profile=request.resume_profile,
        job_analysis=request.job_analysis,
    )
