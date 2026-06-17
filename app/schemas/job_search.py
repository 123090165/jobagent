from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.profile_session import ProfileSession


class JobSearchResult(BaseModel):
    job_result_id: str
    title: str
    company: str
    location: str
    source: Literal["local_mock"] = "local_mock"
    description: str
    matched_keywords: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    match_score: int
    recommended_action: str


class JobSearchRun(BaseModel):
    job_search_run_id: str
    session_id: str
    confirmed_profile_id: str
    query: str
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    status: Literal["completed"] = "completed"
    results: list[JobSearchResult] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class JobSearchRunCreateRequest(BaseModel):
    session_id: str
    query: str | None = None
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class JobSearchRunResponse(BaseModel):
    job_search_run: JobSearchRun
    profile_session: ProfileSession


class JobSearchRunListResponse(BaseModel):
    items: list[JobSearchRun] = Field(default_factory=list)
