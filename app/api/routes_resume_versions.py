from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.resume_version import (
    ResumeVersionCreateRequest,
    ResumeVersionResponse,
    ResumeVersionSummary,
)
from app.services.resume_version_service import (
    list_saved_resume_versions,
    load_resume_version,
    save_resume_version,
)

router = APIRouter(tags=["resume versions"])


@router.get("/resume-versions", response_model=list[ResumeVersionSummary])
def list_resume_version_records(
    limit: int = 20,
    keyword: str | None = None,
    target_job_id: int | None = None,
) -> list[ResumeVersionSummary]:
    versions = list_saved_resume_versions(
        limit=limit,
        keyword=keyword,
        target_job_id=target_job_id,
    )
    return [ResumeVersionSummary.model_validate(version) for version in versions]


@router.post("/resume-versions", response_model=ResumeVersionResponse)
def create_resume_version_record(request: ResumeVersionCreateRequest) -> ResumeVersionResponse:
    version = save_resume_version(
        label=request.label,
        base_resume_text=request.base_resume_text,
        tailored_resume_text=request.tailored_resume_text,
        target_job_id=request.target_job_id,
        source_analysis_record_id=request.source_analysis_record_id,
        notes=request.notes,
    )
    if version is None:
        raise HTTPException(status_code=404, detail="linked job or analysis record not found")
    return ResumeVersionResponse.model_validate(version)


@router.get("/resume-versions/{resume_version_id}", response_model=ResumeVersionResponse)
def get_resume_version_record(resume_version_id: int) -> ResumeVersionResponse:
    version = load_resume_version(resume_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="resume version not found")
    return ResumeVersionResponse.model_validate(version)
