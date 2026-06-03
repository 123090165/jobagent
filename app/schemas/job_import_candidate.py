from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JobImportCandidateStatus = Literal[
    "draft",
    "reviewed",
    "ready_for_tracker",
    "ready_for_analysis",
    "rejected",
]


class JobImportCandidate(BaseModel):
    candidate_id: str
    source: str
    source_run_id: str | None = None
    source_item_id: int | None = None
    title: str
    company: str | None = None
    location: str | None = None
    source_url: str | None = None
    job_type: str | None = None
    education: str | None = None
    deadline: str | None = None
    snippet: str | None = None
    jd_text_preview: str | None = None
    jd_text: str | None = None
    quality_label: str | None = None
    quality_score: float | None = None
    quality_warnings: list[str] = Field(default_factory=list)
    external_links: list[str] = Field(default_factory=list)
    fit_score: float | None = None
    advice: str | None = None
    fit_reasons: list[str] = Field(default_factory=list)
    risk_points: list[str] = Field(default_factory=list)
    status: JobImportCandidateStatus = "draft"
    user_notes: str | None = None
    created_at: str
    updated_at: str
