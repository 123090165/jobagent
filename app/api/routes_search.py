from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import (
    SearchJobsRequest,
    SearchQueriesFromResumeRequest,
    SearchQueriesFromResumeResponse,
)
from app.schemas.search import SearchResultSet
from app.services.job_search_service import search_jobs
from app.services.search_query_service import generate_search_queries_from_resume

router = APIRouter(tags=["search"])


@router.post("/search/jobs", response_model=SearchResultSet)
def search_job_postings(request: SearchJobsRequest) -> SearchResultSet:
    return search_jobs(
        query=request.query,
        provider=request.provider,
        limit=request.limit,
    )


@router.post(
    "/search/queries/from-resume",
    response_model=SearchQueriesFromResumeResponse,
)
def generate_search_queries(request: SearchQueriesFromResumeRequest) -> SearchQueriesFromResumeResponse:
    return SearchQueriesFromResumeResponse(
        queries=generate_search_queries_from_resume(
            resume_text=request.resume_text,
            max_queries=request.max_queries,
        )
    )
