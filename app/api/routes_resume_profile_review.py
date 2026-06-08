from __future__ import annotations

from fastapi import APIRouter

from app.schemas.profile_review import (
    ConfirmedResumeProfileResult,
    ResumeProfileConfirmRequest,
    ResumeProfileReviewRequest,
    ResumeProfileReviewResult,
)
from app.services.resume_profile_review_service import (
    build_resume_profile_review,
    confirm_resume_profile,
)

router = APIRouter(tags=["resume"])


@router.post("/resume/profile-review", response_model=ResumeProfileReviewResult)
def review_resume_profile(
    request: ResumeProfileReviewRequest,
) -> ResumeProfileReviewResult:
    return build_resume_profile_review(
        request.resume_text,
        target_roles=request.target_roles,
    )


@router.post(
    "/resume/profile-review/confirm",
    response_model=ConfirmedResumeProfileResult,
)
def confirm_reviewed_resume_profile(
    request: ResumeProfileConfirmRequest,
) -> ConfirmedResumeProfileResult:
    return confirm_resume_profile(
        request.parsed_profile,
        request.user_edits,
    )
