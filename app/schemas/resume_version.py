from __future__ import annotations

from pydantic import BaseModel, Field


class ResumeVersionCreateRequest(BaseModel):
    label: str = Field(min_length=1)
    base_resume_text: str = Field(min_length=1)
    tailored_resume_text: str | None = None
    target_job_id: int | None = None
    source_analysis_record_id: int | None = None
    notes: str | None = None


class ResumeVersionResponse(BaseModel):
    id: int
    label: str
    base_resume_text: str
    tailored_resume_text: str | None = None
    target_job_id: int | None = None
    target_job_title: str | None = None
    target_company: str | None = None
    source_analysis_record_id: int | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class ResumeVersionSummary(BaseModel):
    id: int
    label: str
    target_job_id: int | None = None
    target_job_title: str | None = None
    target_company: str | None = None
    source_analysis_record_id: int | None = None
    notes: str | None = None
    created_at: str
    updated_at: str
