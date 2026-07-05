from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SavedJobStatus = Literal["saved", "interested", "applied", "rejected", "archived"]


class SavedJobAnalysis(BaseModel):
    saved_job_analysis_id: str
    saved_job_id: str
    user_id: str
    resume_profile_id: str | None = None
    source_job_search_run_id: str | None = None
    source_job_result_id: str | None = None
    match_score: int | None = None
    confidence_label: str | None = None
    recommendation: str | None = None
    matched_strengths: list[str] = Field(default_factory=list)
    critical_gaps: list[str] = Field(default_factory=list)
    resume_actions: list[str] = Field(default_factory=list)
    interview_questions: list[str] = Field(default_factory=list)
    analysis: dict[str, object] = Field(default_factory=dict)
    analysis_mode: str
    created_at: datetime


class SavedJob(BaseModel):
    saved_job_id: str
    user_id: str
    source_provider: str | None = None
    source_url: str | None = None
    normalized_source_key: str | None = None
    title: str
    company: str | None = None
    location: str | None = None
    salary: str | None = None
    employment_type: str | None = None
    raw_jd_text: str
    structured_jd: dict[str, object] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    status: SavedJobStatus = "saved"
    notes: str | None = None
    first_seen_at: datetime
    saved_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    latest_analysis: SavedJobAnalysis | None = None


class SavedJobCreateRequest(BaseModel):
    source_provider: str | None = None
    source_url: str | None = None
    title: str
    company: str | None = None
    location: str | None = None
    salary: str | None = None
    employment_type: str | None = None
    raw_jd_text: str
    structured_jd: dict[str, object] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    status: SavedJobStatus = "saved"
    notes: str | None = None

    @field_validator("title", "raw_jd_text")
    @classmethod
    def _required_string(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be empty")
        return cleaned


class SavedJobUpdateRequest(BaseModel):
    status: SavedJobStatus | None = None
    notes: str | None = None
    tags: list[str] | None = None


class SavedJobFromSearchResultRequest(BaseModel):
    job_search_run_id: str
    job_result_id: str
    resume_profile_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: SavedJobStatus = "saved"
    notes: str | None = None


class SavedJobFromBrowserCaptureRequest(SavedJobCreateRequest):
    analysis: dict[str, object] | None = None
    resume_profile_id: str | None = None
    match_score: int | None = None
    confidence_label: str | None = None
    recommendation: str | None = None


class SavedJobListResponse(BaseModel):
    items: list[SavedJob] = Field(default_factory=list)
