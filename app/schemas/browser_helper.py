from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BrowserHelperProfileSessionOption(BaseModel):
    session_id: str
    resume_profile_id: str | None = None
    label: str
    is_default: bool = False


class BrowserHelperSavedJobOption(BaseModel):
    saved_job_id: str
    title: str
    company: str | None = None


class BrowserHelperContextCatalog(BaseModel):
    saved_jobs: list[BrowserHelperSavedJobOption] = Field(default_factory=list)


class BrowserHelperSessionCreateResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    profile_sessions: list[BrowserHelperProfileSessionOption] = Field(default_factory=list)
