from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_current_user
from app.application.resume_profile_usecases import (
    archive_resume_profile,
    delete_resume_profile,
    get_resume_profile,
    list_resume_profiles,
    set_default_resume_profile,
    restore_resume_profile,
    update_resume_profile,
)
from app.schemas.auth import UserAccount
from app.schemas.resume_profile import (
    ResumeProfile,
    ResumeProfileListResponse,
    ResumeProfileUpdateRequest,
)

router = APIRouter(prefix="/api/v1/resume-profiles", tags=["v4-resume-profiles"])


@router.get("", response_model=ResumeProfileListResponse)
def list_resume_profiles_endpoint(
    include_archived: bool = Query(default=False),
    current_user: UserAccount = Depends(get_current_user),
) -> ResumeProfileListResponse:
    return ResumeProfileListResponse(
        items=list_resume_profiles(
            user_id=current_user.user_id,
            include_archived=include_archived,
        )
    )


@router.get("/{resume_profile_id}", response_model=ResumeProfile)
def get_resume_profile_endpoint(
    resume_profile_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ResumeProfile:
    return get_resume_profile(resume_profile_id, user_id=current_user.user_id)


@router.patch("/{resume_profile_id}", response_model=ResumeProfile)
def update_resume_profile_endpoint(
    resume_profile_id: str,
    payload: ResumeProfileUpdateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> ResumeProfile:
    return update_resume_profile(
        resume_profile_id,
        payload,
        user_id=current_user.user_id,
    )


@router.post("/{resume_profile_id}/default", response_model=ResumeProfile)
def set_default_resume_profile_endpoint(
    resume_profile_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ResumeProfile:
    return set_default_resume_profile(resume_profile_id, user_id=current_user.user_id)


@router.post("/{resume_profile_id}/archive", response_model=ResumeProfile)
def archive_resume_profile_endpoint(
    resume_profile_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ResumeProfile:
    return archive_resume_profile(resume_profile_id, user_id=current_user.user_id)


@router.post("/{resume_profile_id}/restore", response_model=ResumeProfile)
def restore_resume_profile_endpoint(
    resume_profile_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ResumeProfile:
    return restore_resume_profile(resume_profile_id, user_id=current_user.user_id)


@router.delete("/{resume_profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume_profile_endpoint(
    resume_profile_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> Response:
    delete_resume_profile(resume_profile_id, user_id=current_user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
