from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import (
    CreateJobImportCandidateFromBriefRequest,
    JobImportCandidateResponse,
    ListJobImportCandidatesResponse,
    UpdateJobImportCandidateRequest,
)
from app.services.errors import JobAgentError
from app.services.job_import_candidate_service import (
    create_candidate_from_brief_run,
    get_candidate,
    list_candidates,
    update_candidate,
)

router = APIRouter(tags=["job-candidates"])


@router.post("/job-candidates/from-brief-run", response_model=JobImportCandidateResponse)
def create_job_candidate_from_brief_run(
    request: CreateJobImportCandidateFromBriefRequest,
) -> JobImportCandidateResponse:
    candidate = create_candidate_from_brief_run(
        run_id=request.run_id,
        item_id=request.item_id,
        rank=request.rank,
    )
    return JobImportCandidateResponse(candidate=candidate)


@router.get("/job-candidates/{candidate_id}", response_model=JobImportCandidateResponse)
def get_job_candidate(
    candidate_id: str,
    include_full_jd: bool = False,
) -> JobImportCandidateResponse:
    candidate = get_candidate(candidate_id, include_full_jd=include_full_jd)
    if candidate is None:
        raise JobAgentError(
            "Job import candidate not found",
            "job_import_candidate_not_found",
            status_code=404,
        )
    return JobImportCandidateResponse(candidate=candidate)


@router.get("/job-candidates", response_model=ListJobImportCandidatesResponse)
def list_job_candidates(
    status: str | None = None,
    limit: int = 20,
) -> ListJobImportCandidatesResponse:
    return ListJobImportCandidatesResponse(candidates=list_candidates(status=status, limit=limit))


@router.patch("/job-candidates/{candidate_id}", response_model=JobImportCandidateResponse)
def patch_job_candidate(
    candidate_id: str,
    request: UpdateJobImportCandidateRequest,
) -> JobImportCandidateResponse:
    candidate = update_candidate(
        candidate_id,
        title=request.title,
        company=request.company,
        location=request.location,
        job_type=request.job_type,
        education=request.education,
        deadline=request.deadline,
        status=request.status,
        user_notes=request.user_notes,
    )
    return JobImportCandidateResponse(candidate=candidate)
