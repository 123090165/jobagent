from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_current_user
from app.application.tailored_resume_usecases import (
    approve_application_resume,
    export_approved_resume_pdf,
    update_application_resume,
)
from app.schemas.auth import UserAccount
from app.schemas.tailored_resume import TailoredResumeUpdateRequest, TailoredResumeVersion


router = APIRouter(prefix="/api/v1/tailored-resumes", tags=["v4-tailored-resumes"])


@router.patch("/{tailored_resume_id}", response_model=TailoredResumeVersion)
def update_tailored_resume_endpoint(
    tailored_resume_id: str,
    payload: TailoredResumeUpdateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> TailoredResumeVersion:
    return update_application_resume(tailored_resume_id, payload, user_id=current_user.user_id)


@router.post("/{tailored_resume_id}/approve", response_model=TailoredResumeVersion)
def approve_tailored_resume_endpoint(
    tailored_resume_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> TailoredResumeVersion:
    return approve_application_resume(tailored_resume_id, user_id=current_user.user_id)


@router.get("/{tailored_resume_id}/pdf")
def download_tailored_resume_pdf_endpoint(
    tailored_resume_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> StreamingResponse:
    payload, filename = export_approved_resume_pdf(
        tailored_resume_id,
        user_id=current_user.user_id,
    )
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
