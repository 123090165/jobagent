from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TailoredResumeStatus = Literal["needs_review", "approved"]


class ResumeFactValidation(BaseModel):
    is_valid: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TailoredResumeVersion(BaseModel):
    tailored_resume_id: str
    user_id: str
    saved_job_id: str
    resume_profile_id: str
    version: int
    content: str
    validation: ResumeFactValidation
    status: TailoredResumeStatus
    analysis_provider: str | None = None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None


class TailoredResumeGenerateRequest(BaseModel):
    resume_profile_id: str | None = None
    llm_provider: str | None = None


class TailoredResumeUpdateRequest(BaseModel):
    content: str = Field(min_length=1)
