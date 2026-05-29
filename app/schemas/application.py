from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

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
    resume_version_label: str | None = None


class ApplicationUpdateRequest(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None
    next_action: str | None = None
    resume_version_label: str | None = None


class ApplicationRecordResponse(BaseModel):
    id: int
    job_id: int
    status: ApplicationStatus
    notes: str | None = None
    next_action: str | None = None
    resume_version_label: str | None = None
    job_title: str | None = None
    company: str | None = None
    created_at: str
    updated_at: str
