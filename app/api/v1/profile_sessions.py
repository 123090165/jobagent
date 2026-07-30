"""定义 简历到搜索的流程会话 的 HTTP 接口，并把已验证请求和当前用户交给 application 用例。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.api.dependencies import get_current_user
from app.application.profile_session_usecases import (
    create_profile_session,
    get_profile_session,
)
from app.application.job_search_usecases import list_job_search_runs
from app.application.profile_draft_usecases import create_profile_draft
from app.application.resume_intake_usecases import (
    get_resume_document,
    submit_resume_file,
    submit_resume_text,
)
from app.application.resume_review_usecases import (
    get_parsed_resume_review,
    parse_resume_for_review,
)
from app.application.search_mission_usecases import (
    confirm_search_mission,
    get_search_mission,
    interpret_saved_search_mission,
    save_search_mission_input,
)
from app.schemas.auth import UserAccount
from app.schemas.job_search import JobSearchRunListResponse
from app.schemas.parsed_resume_review import ParsedResumeReviewResponse
from app.schemas.profile_draft import ProfileDraftResponse
from app.schemas.profile_session import ProfileSession
from app.schemas.resume_document import ResumeDocument
from app.schemas.resume_intake import ResumeIntakeResponse, ResumeTextRequest
from app.schemas.search_mission import (
    SearchMission,
    SearchMissionInput,
    SearchMissionInterpretRequest,
)

router = APIRouter(prefix="/api/v1/profile-sessions", tags=["v4-profile-sessions"])


@router.post("", response_model=ProfileSession, status_code=status.HTTP_201_CREATED)
def create_profile_session_endpoint(
    current_user: UserAccount = Depends(get_current_user),
) -> ProfileSession:
    return create_profile_session(user_id=current_user.user_id)


@router.get("/{session_id}", response_model=ProfileSession)
def get_profile_session_endpoint(
    session_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ProfileSession:
    return get_profile_session(session_id, user_id=current_user.user_id)


@router.post(
    "/{session_id}/resume-text",
    response_model=ResumeIntakeResponse,
)
def submit_resume_text_endpoint(
    session_id: str,
    payload: ResumeTextRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> ResumeIntakeResponse:
    return submit_resume_text(session_id, payload.text, user_id=current_user.user_id)


@router.post(
    "/{session_id}/resume-file",
    response_model=ResumeIntakeResponse,
)
async def submit_resume_file_endpoint(
    session_id: str,
    file: UploadFile = File(...),
    current_user: UserAccount = Depends(get_current_user),
) -> ResumeIntakeResponse:
    return await submit_resume_file(session_id, file, user_id=current_user.user_id)


@router.get("/{session_id}/resume", response_model=ResumeDocument)
def get_resume_document_endpoint(
    session_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ResumeDocument:
    return get_resume_document(session_id, user_id=current_user.user_id)


@router.post(
    "/{session_id}/parse-resume",
    response_model=ParsedResumeReviewResponse,
)
def parse_resume_for_review_endpoint(
    session_id: str,
    regenerate: bool = Query(default=False),
    use_llm: bool = Query(default=False),
    current_user: UserAccount = Depends(get_current_user),
) -> ParsedResumeReviewResponse:
    return parse_resume_for_review(
        session_id,
        regenerate=regenerate,
        use_llm=use_llm,
        user_id=current_user.user_id,
    )


@router.get(
    "/{session_id}/parsed-review",
    response_model=ParsedResumeReviewResponse,
)
def get_parsed_resume_review_endpoint(
    session_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> ParsedResumeReviewResponse:
    return get_parsed_resume_review(session_id, user_id=current_user.user_id)


@router.post(
    "/{session_id}/profile-draft",
    response_model=ProfileDraftResponse,
)
def create_profile_draft_endpoint(
    session_id: str,
    regenerate: bool = Query(default=False),
    current_user: UserAccount = Depends(get_current_user),
) -> ProfileDraftResponse:
    return create_profile_draft(
        session_id,
        regenerate=regenerate,
        user_id=current_user.user_id,
    )


@router.get(
    "/{session_id}/job-search-runs",
    response_model=JobSearchRunListResponse,
)
def list_job_search_runs_endpoint(
    session_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> JobSearchRunListResponse:
    return JobSearchRunListResponse(
        items=list_job_search_runs(session_id, user_id=current_user.user_id)
    )


@router.get("/{session_id}/search-mission", response_model=SearchMission)
def get_search_mission_endpoint(
    session_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> SearchMission:
    return get_search_mission(session_id, user_id=current_user.user_id)


@router.put("/{session_id}/search-mission", response_model=SearchMission)
def save_search_mission_endpoint(
    session_id: str,
    payload: SearchMissionInput,
    current_user: UserAccount = Depends(get_current_user),
) -> SearchMission:
    return save_search_mission_input(session_id, payload, user_id=current_user.user_id)


@router.post("/{session_id}/search-mission/interpret", response_model=SearchMission)
def interpret_search_mission_endpoint(
    session_id: str,
    payload: SearchMissionInterpretRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> SearchMission:
    return interpret_saved_search_mission(
        session_id,
        user_id=current_user.user_id,
        use_llm=payload.use_llm,
        llm_provider=payload.llm_provider,
    )


@router.post("/{session_id}/search-mission/confirm", response_model=SearchMission)
def confirm_search_mission_endpoint(
    session_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> SearchMission:
    return confirm_search_mission(session_id, user_id=current_user.user_id)
