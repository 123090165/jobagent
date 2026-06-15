from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ProfileSessionStatus(str, Enum):
    active = "active"
    completed = "completed"
    archived = "archived"


class ProfileSessionStep(str, Enum):
    resume_intake = "resume_intake"
    resume_review = "resume_review"
    profile_draft = "profile_draft"
    profile_confirmed = "profile_confirmed"
    job_search_ready = "job_search_ready"


class ProfileSession(BaseModel):
    session_id: str
    status: ProfileSessionStatus
    created_at: datetime
    updated_at: datetime
    resume_document_id: str | None = None
    parsed_review_id: str | None = None
    profile_draft_id: str | None = None
    confirmed_profile_id: str | None = None
    current_step: ProfileSessionStep
