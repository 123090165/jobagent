from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import BriefFromSearchRequest
from app.schemas.brief import JobBriefReport
from app.services.batch_brief_service import build_brief_from_search

router = APIRouter(tags=["brief"])


@router.post("/brief/from-search", response_model=JobBriefReport)
def generate_brief_from_search(request: BriefFromSearchRequest) -> JobBriefReport:
    return build_brief_from_search(
        resume_text=request.resume_text,
        query=request.query,
        provider=request.provider,
        limit=request.limit,
        use_llm_jd=request.use_llm_jd,
    )
