from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chat_or_browser_helper_user
from app.application.browser_helper_usecases import (
    analyze_saved_browser_job_capture,
    save_browser_job_capture,
)
from app.application.communication_usecases import generate_browser_greeting_draft
from app.application.tailored_resume_usecases import generate_browser_capture_resume
from app.schemas.auth import UserAccount
from app.schemas.communication import CommunicationDraft, CommunicationDraftGenerateRequest
from app.schemas.job_search import (
    BrowserJobCaptureAnalyzeResponse,
    BrowserJobCaptureAnalysisRequest,
    BrowserJobCaptureCreateRequest,
    BrowserJobCaptureCreateResponse,
)
from app.schemas.tailored_resume import TailoredResumeGenerateRequest, TailoredResumeVersion

router = APIRouter(prefix="/api/v1/browser/job-captures", tags=["v4-browser-job-captures"])


@router.post("", response_model=BrowserJobCaptureCreateResponse, status_code=201)
def save_browser_job_capture_endpoint(
    payload: BrowserJobCaptureCreateRequest,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> BrowserJobCaptureCreateResponse:
    return save_browser_job_capture(payload, user_id=current_user.user_id)


@router.post("/{capture_id}/analyze", response_model=BrowserJobCaptureAnalyzeResponse)
def analyze_saved_browser_job_capture_endpoint(
    capture_id: str,
    payload: BrowserJobCaptureAnalysisRequest,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> BrowserJobCaptureAnalyzeResponse:
    return analyze_saved_browser_job_capture(
        capture_id,
        payload,
        user_id=current_user.user_id,
    )


@router.post("/{capture_id}/greeting-drafts", response_model=CommunicationDraft, status_code=201)
def generate_browser_greeting_draft_endpoint(
    capture_id: str,
    payload: CommunicationDraftGenerateRequest,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> CommunicationDraft:
    return generate_browser_greeting_draft(
        capture_id,
        payload,
        user_id=current_user.user_id,
    )


@router.post("/{capture_id}/tailored-resumes", response_model=TailoredResumeVersion, status_code=201)
def generate_browser_tailored_resume_endpoint(
    capture_id: str,
    payload: TailoredResumeGenerateRequest,
    current_user: UserAccount = Depends(get_chat_or_browser_helper_user),
) -> TailoredResumeVersion:
    return generate_browser_capture_resume(capture_id, payload, user_id=current_user.user_id)
