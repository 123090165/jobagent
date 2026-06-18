from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.job_search_provider import JobSearchProviderStatusResponse
from app.services.job_search_providers import get_job_search_provider_status

router = APIRouter(prefix="/api/v1/job-search-providers", tags=["v4-job-search-providers"])


@router.get("/status", response_model=JobSearchProviderStatusResponse)
def get_job_search_provider_status_endpoint(
    provider: str | None = Query(default=None),
) -> JobSearchProviderStatusResponse:
    return JobSearchProviderStatusResponse.model_validate(get_job_search_provider_status(provider))
