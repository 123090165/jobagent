from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.jd_analysis_agent import analyze_jd
from app.schemas.api import (
    JDAnalysisRequest,
    JDUrlImportRequest,
    JDUrlImportResponse,
    JobPostingResponse,
    JobPostingSummary,
)
from app.schemas.job import JobAnalysis
from app.services.errors import JobAgentError
from app.services.jd_url_service import import_jd_from_url
from app.services.storage_service import list_saved_job_postings, load_job_posting

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=list[JobPostingSummary])
def list_jobs(limit: int = 20, keyword: str | None = None) -> list[JobPostingSummary]:
    jobs = list_saved_job_postings(limit=limit, keyword=keyword)
    return [JobPostingSummary.model_validate(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobPostingResponse)
def get_job(job_id: int) -> JobPostingResponse:
    job = load_job_posting(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobPostingResponse.model_validate(job)


@router.post("/jobs/analyze", response_model=JobAnalysis)
def analyze_job(request: JDAnalysisRequest) -> JobAnalysis:
    try:
        return analyze_jd(request.jd_text, use_llm=request.use_llm)
    except ValueError as exc:
        raise JobAgentError(str(exc), "jd_input_invalid") from exc


@router.post("/jobs/import-url", response_model=JDUrlImportResponse)
def import_job_from_url(request: JDUrlImportRequest) -> JDUrlImportResponse:
    extracted_text = import_jd_from_url(request.url)
    return JDUrlImportResponse(
        url=request.url.strip(),
        extracted_text=extracted_text,
        warning=None,
    )
