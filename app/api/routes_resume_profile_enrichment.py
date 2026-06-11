from __future__ import annotations

from fastapi import APIRouter

from app.schemas.profile_enrichment import (
    ResumeProfileEnrichmentRequest,
    ResumeProfileEnrichmentResult,
)
from app.services.resume_profile_enrichment_service import (
    build_resume_profile_enrichment,
)

router = APIRouter(tags=["resume"])


@router.post(
    "/resume/profile-enrichment",
    response_model=ResumeProfileEnrichmentResult,
)
def enrich_resume_profile(
    request: ResumeProfileEnrichmentRequest,
) -> ResumeProfileEnrichmentResult:
    return build_resume_profile_enrichment(
        resume_text=request.resume_text,
        target_roles=request.target_roles,
        use_llm=request.use_llm,
    )
