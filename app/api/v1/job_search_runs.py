from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status

from app.api.dependencies import get_current_user
from app.application.job_search_usecases import (
    create_browser_helper_job_search_run,
    create_job_search_run,
    delete_job_search_run,
    get_job_search_run,
    list_user_job_search_runs,
    list_job_search_trace_steps,
    preview_job_search_run,
)
from app.application.job_search_feedback_usecases import (
    list_result_feedback,
    upsert_result_feedback,
)
from app.schemas.auth import UserAccount
from app.schemas.job_search import (
    BrowserHelperJobSearchRunCreateRequest,
    JobSearchPreviewResponse,
    JobSearchRunCreateRequest,
    JobSearchRunResponse,
    JobSearchRunListResponse,
    JobSearchTraceStepListResponse,
)
from app.schemas.job_search_feedback import (
    JobSearchResultFeedback,
    JobSearchResultFeedbackListResponse,
    JobSearchResultFeedbackUpsertRequest,
)

router = APIRouter(prefix="/api/v1/job-search-runs", tags=["v4-job-search-runs"])


@router.get("", response_model=JobSearchRunListResponse)
def list_user_job_search_runs_endpoint(
    limit: int = Query(default=100, ge=1, le=200),
    current_user: UserAccount = Depends(get_current_user),
) -> JobSearchRunListResponse:
    return JobSearchRunListResponse(
        items=list_user_job_search_runs(user_id=current_user.user_id, limit=limit)
    )


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_search_run_endpoint(
    run_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> Response:
    delete_job_search_run(run_id, user_id=current_user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("", response_model=JobSearchRunResponse)
def create_job_search_run_endpoint(
    background_tasks: BackgroundTasks,
    payload: JobSearchRunCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> JobSearchRunResponse:
    return create_job_search_run(
        payload,
        background_tasks=background_tasks,
        user_id=current_user.user_id,
    )


@router.post("/preview", response_model=JobSearchPreviewResponse)
def preview_job_search_run_endpoint(
    payload: JobSearchRunCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> JobSearchPreviewResponse:
    return preview_job_search_run(payload, user_id=current_user.user_id)


@router.post("/browser-helper", response_model=JobSearchRunResponse)
def create_browser_helper_job_search_run_endpoint(
    background_tasks: BackgroundTasks,
    payload: BrowserHelperJobSearchRunCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> JobSearchRunResponse:
    return create_browser_helper_job_search_run(
        payload,
        background_tasks=background_tasks,
        user_id=current_user.user_id,
    )


@router.get("/{run_id}", response_model=JobSearchRunResponse)
def get_job_search_run_endpoint(
    run_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> JobSearchRunResponse:
    return get_job_search_run(run_id, user_id=current_user.user_id)


@router.get("/{run_id}/steps", response_model=JobSearchTraceStepListResponse)
def list_job_search_run_steps_endpoint(
    run_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> JobSearchTraceStepListResponse:
    return JobSearchTraceStepListResponse(
        items=list_job_search_trace_steps(run_id, user_id=current_user.user_id)
    )


@router.get("/{run_id}/feedback", response_model=JobSearchResultFeedbackListResponse)
def list_result_feedback_endpoint(
    run_id: str,
    current_user: UserAccount = Depends(get_current_user),
) -> JobSearchResultFeedbackListResponse:
    return JobSearchResultFeedbackListResponse(
        items=list_result_feedback(run_id, user_id=current_user.user_id)
    )


@router.post(
    "/{run_id}/results/{result_id}/feedback",
    response_model=JobSearchResultFeedback,
)
def upsert_result_feedback_endpoint(
    run_id: str,
    result_id: str,
    payload: JobSearchResultFeedbackUpsertRequest,
    current_user: UserAccount = Depends(get_current_user),
) -> JobSearchResultFeedback:
    return upsert_result_feedback(
        run_id,
        result_id,
        payload,
        user_id=current_user.user_id,
    )
