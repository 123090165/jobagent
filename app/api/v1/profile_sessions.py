from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile, status

from app.application.profile_session_usecases import (
    create_profile_session,
    get_profile_session,
)
from app.application.resume_intake_usecases import (
    get_resume_document,
    submit_resume_file,
    submit_resume_text,
)
from app.application.resume_review_usecases import (
    get_parsed_resume_review,
    parse_resume_for_review,
)
from app.schemas.parsed_resume_review import ParsedResumeReviewResponse
from app.schemas.profile_session import ProfileSession
from app.schemas.resume_document import ResumeDocument
from app.schemas.resume_intake import ResumeIntakeResponse, ResumeTextRequest

router = APIRouter(prefix="/api/v1/profile-sessions", tags=["v4-profile-sessions"])


@router.post("", response_model=ProfileSession, status_code=status.HTTP_201_CREATED)
def create_profile_session_endpoint() -> ProfileSession:
    return create_profile_session()


@router.get("/{session_id}", response_model=ProfileSession)
def get_profile_session_endpoint(session_id: str) -> ProfileSession:
    return get_profile_session(session_id)


@router.post(
    "/{session_id}/resume-text",
    response_model=ResumeIntakeResponse,
)
def submit_resume_text_endpoint(
    session_id: str,
    payload: ResumeTextRequest,
) -> ResumeIntakeResponse:
    return submit_resume_text(session_id, payload.text)


@router.post(
    "/{session_id}/resume-file",
    response_model=ResumeIntakeResponse,
)
async def submit_resume_file_endpoint(
    session_id: str,
    file: UploadFile = File(...),
) -> ResumeIntakeResponse:
    return await submit_resume_file(session_id, file)


@router.get("/{session_id}/resume", response_model=ResumeDocument)
def get_resume_document_endpoint(session_id: str) -> ResumeDocument:
    return get_resume_document(session_id)


@router.post(
    "/{session_id}/parse-resume",
    response_model=ParsedResumeReviewResponse,
)
def parse_resume_for_review_endpoint(
    session_id: str,
    regenerate: bool = Query(default=False),
) -> ParsedResumeReviewResponse:
    return parse_resume_for_review(session_id, regenerate=regenerate)


@router.get(
    "/{session_id}/parsed-review",
    response_model=ParsedResumeReviewResponse,
)
def get_parsed_resume_review_endpoint(session_id: str) -> ParsedResumeReviewResponse:
    return get_parsed_resume_review(session_id)
