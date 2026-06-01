from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import SearchJobsRequest
from app.schemas.search import SearchResultSet
from app.services.job_search_service import search_jobs

router = APIRouter(tags=["search"])


@router.post("/search/jobs", response_model=SearchResultSet)
def search_job_postings(request: SearchJobsRequest) -> SearchResultSet:
    return search_jobs(
        query=request.query,
        provider=request.provider,
        limit=request.limit,
    )
