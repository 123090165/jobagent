from __future__ import annotations

from fastapi import APIRouter

from app.application.job_search_usecases import (
    create_job_search_run,
    get_job_search_run,
)
from app.schemas.job_search import JobSearchRunCreateRequest, JobSearchRunResponse

router = APIRouter(prefix="/api/v1/job-search-runs", tags=["v4-job-search-runs"])


@router.post("", response_model=JobSearchRunResponse)
def create_job_search_run_endpoint(
    payload: JobSearchRunCreateRequest,
) -> JobSearchRunResponse:
    return create_job_search_run(payload)


@router.get("/{run_id}", response_model=JobSearchRunResponse)
def get_job_search_run_endpoint(run_id: str) -> JobSearchRunResponse:
    return get_job_search_run(run_id)
