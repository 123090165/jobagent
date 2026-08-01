from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.application.application_tracking_usecases import update_job_application
from app.schemas.auth import UserAccount
from app.schemas.job_application import JobApplication, JobApplicationUpdateRequest

router = APIRouter(prefix="/api/v1/job-applications", tags=["v4-job-applications"])


@router.patch("/{application_id}", response_model=JobApplication)
def update_job_application_endpoint(
    application_id: str,
    payload: JobApplicationUpdateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> JobApplication:
    return update_job_application(
        application_id,
        payload,
        user_id=current_user.user_id,
    )
