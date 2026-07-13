from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import PlainTextResponse

from app.api.dependencies import get_current_user
from app.application.saved_job_usecases import (
    archive_saved_job,
    create_saved_job,
    delete_saved_job,
    get_saved_job,
    generate_job_brief,
    generate_interview_preparation,
    get_interview_preparation,
    complete_interview_preparation,
    export_interview_preparation_prompt,
    list_job_briefs,
    list_saved_jobs,
    list_saved_job_analyses,
    list_saved_job_status_events,
    save_job_from_browser_capture,
    save_job_from_search_result,
    update_saved_job,
)
from app.schemas.auth import UserAccount
from app.schemas.job_brief import JobBrief, JobBriefGenerateRequest, JobBriefListResponse
from app.schemas.interview_preparation import (
    InterviewPreparationWorkspace,
    PreparationAnswerRequest,
    PreparationGenerateRequest,
)
from app.schemas.saved_job import (
    SavedJob,
    SavedJobAnalysisListResponse,
    SavedJobCreateRequest,
    SavedJobFromBrowserCaptureRequest,
    SavedJobFromSearchResultRequest,
    SavedJobListResponse,
    SavedJobUpdateRequest,
    SavedJobStatusEventListResponse,
)

router = APIRouter(prefix="/api/v1/saved-jobs", tags=["v4-saved-jobs"])


@router.get("", response_model=SavedJobListResponse)
def list_saved_jobs_endpoint(
    include_archived: bool = Query(default=False),
    current_user: UserAccount = Depends(get_current_user),
) -> SavedJobListResponse:
    return SavedJobListResponse(
        items=list_saved_jobs(
            user_id=current_user.user_id,
            include_archived=include_archived,
        )
    )


@router.post("", response_model=SavedJob)
def create_saved_job_endpoint(
    payload: SavedJobCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> SavedJob:
    return create_saved_job(payload, user_id=current_user.user_id)


@router.post("/from-search-result", response_model=SavedJob)
def save_job_from_search_result_endpoint(
    payload: SavedJobFromSearchResultRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> SavedJob:
    return save_job_from_search_result(payload, user_id=current_user.user_id)


@router.post("/from-browser-capture", response_model=SavedJob)
def save_job_from_browser_capture_endpoint(
    payload: SavedJobFromBrowserCaptureRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> SavedJob:
    return save_job_from_browser_capture(payload, user_id=current_user.user_id)


@router.get("/{saved_job_id}", response_model=SavedJob)
def get_saved_job_endpoint(
    saved_job_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> SavedJob:
    return get_saved_job(saved_job_id, user_id=current_user.user_id)


@router.get("/{saved_job_id}/analyses", response_model=SavedJobAnalysisListResponse)
def list_saved_job_analyses_endpoint(
    saved_job_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> SavedJobAnalysisListResponse:
    return SavedJobAnalysisListResponse(
        items=list_saved_job_analyses(saved_job_id, user_id=current_user.user_id)
    )


@router.get("/{saved_job_id}/status-history", response_model=SavedJobStatusEventListResponse)
def list_saved_job_status_events_endpoint(
    saved_job_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> SavedJobStatusEventListResponse:
    return SavedJobStatusEventListResponse(
        items=list_saved_job_status_events(saved_job_id, user_id=current_user.user_id)
    )


@router.get("/{saved_job_id}/briefs", response_model=JobBriefListResponse)
def list_job_briefs_endpoint(
    saved_job_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> JobBriefListResponse:
    return JobBriefListResponse(items=list_job_briefs(saved_job_id, user_id=current_user.user_id))


@router.post("/{saved_job_id}/briefs", response_model=JobBrief)
def generate_job_brief_endpoint(
    saved_job_id: str,
    payload: JobBriefGenerateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> JobBrief:
    return generate_job_brief(saved_job_id, payload, user_id=current_user.user_id)


@router.get("/{saved_job_id}/preparation", response_model=InterviewPreparationWorkspace)
def get_interview_preparation_endpoint(
    saved_job_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> InterviewPreparationWorkspace:
    return get_interview_preparation(saved_job_id, user_id=current_user.user_id)


@router.post("/{saved_job_id}/preparation", response_model=InterviewPreparationWorkspace)
async def generate_interview_preparation_endpoint(
    saved_job_id: str,
    payload: PreparationGenerateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> InterviewPreparationWorkspace:
    return await generate_interview_preparation(saved_job_id, payload, user_id=current_user.user_id)


@router.put("/{saved_job_id}/preparation/answers", response_model=InterviewPreparationWorkspace)
def complete_interview_preparation_endpoint(
    saved_job_id: str,
    payload: PreparationAnswerRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> InterviewPreparationWorkspace:
    return complete_interview_preparation(saved_job_id, payload, user_id=current_user.user_id)


@router.get("/{saved_job_id}/preparation/prompt.txt", response_class=PlainTextResponse)
def export_interview_preparation_prompt_endpoint(
    saved_job_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> PlainTextResponse:
    text = export_interview_preparation_prompt(saved_job_id, user_id=current_user.user_id)
    return PlainTextResponse(
        text,
        headers={"Content-Disposition": 'attachment; filename="interview-preparation-prompt.txt"'},
    )


@router.patch("/{saved_job_id}", response_model=SavedJob)
def update_saved_job_endpoint(
    saved_job_id: str,
    payload: SavedJobUpdateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> SavedJob:
    return update_saved_job(saved_job_id, payload, user_id=current_user.user_id)


@router.post("/{saved_job_id}/archive", response_model=SavedJob)
def archive_saved_job_endpoint(
    saved_job_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> SavedJob:
    return archive_saved_job(saved_job_id, user_id=current_user.user_id)


@router.delete("/{saved_job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_job_endpoint(
    saved_job_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> Response:
    delete_saved_job(saved_job_id, user_id=current_user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
