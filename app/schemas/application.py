from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ApplicationStatus = Literal[
    "interested",
    "applied",
    "interviewing",
    "rejected",
    "offer",
    "archived",
]


class ApplicationCreateRequest(BaseModel):
    job_id: int
    status: ApplicationStatus = "interested"
    notes: str | None = None
    next_action: str | None = None
    resume_version_id: int | None = None
    resume_version_label: str | None = None


class ApplicationUpdateRequest(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None
    next_action: str | None = None
    resume_version_id: int | None = None
    resume_version_label: str | None = None


class ApplicationAnalysisSummary(BaseModel):
    analysis_count: int = 0
    latest_analysis_record_id: int | None = None
    last_analyzed_at: str | None = None
    last_match_score: float | None = None
    last_analysis_quality: str | None = None
    latest_report_title: str | None = None
    has_analysis: bool = False


class ApplicationRecordResponse(BaseModel):
    id: int
    job_id: int
    status: ApplicationStatus
    notes: str | None = None
    next_action: str | None = None
    resume_version_id: int | None = None
    resume_version_label: str | None = None
    job_title: str | None = None
    company: str | None = None
    created_at: str
    updated_at: str
    analysis_summary: ApplicationAnalysisSummary = Field(default_factory=ApplicationAnalysisSummary)
