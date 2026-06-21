from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app.application.job_search_usecases import (
    create_job_search_run,
    get_job_search_run,
    list_job_search_trace_steps,
    preview_job_search_run,
)
from app.schemas.job_search import (
    JobSearchPreviewResponse,
    JobSearchRunCreateRequest,
    JobSearchRunResponse,
    JobSearchTraceStepListResponse,
)

router = APIRouter(prefix="/api/v1/job-search-runs", tags=["v4-job-search-runs"])


@router.post("", response_model=JobSearchRunResponse)
def create_job_search_run_endpoint(
    background_tasks: BackgroundTasks,
    payload: JobSearchRunCreateRequest,
) -> JobSearchRunResponse:
    return create_job_search_run(payload, background_tasks=background_tasks)


@router.post("/preview", response_model=JobSearchPreviewResponse)
def preview_job_search_run_endpoint(payload: JobSearchRunCreateRequest) -> JobSearchPreviewResponse:
    return preview_job_search_run(payload)


@router.get("/{run_id}", response_model=JobSearchRunResponse)
def get_job_search_run_endpoint(run_id: str) -> JobSearchRunResponse:
    return get_job_search_run(run_id)


@router.get("/{run_id}/steps", response_model=JobSearchTraceStepListResponse)
def list_job_search_run_steps_endpoint(run_id: str) -> JobSearchTraceStepListResponse:
    return JobSearchTraceStepListResponse(items=list_job_search_trace_steps(run_id))
