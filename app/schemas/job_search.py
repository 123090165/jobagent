from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field

from app.schemas.profile_session import ProfileSession

JobSearchMode: TypeAlias = Literal["local_mock", "live_search"]
JobSearchRunStatus: TypeAlias = Literal["pending", "running", "completed", "failed"]
JobSearchStepStatus: TypeAlias = Literal["pending", "running", "completed", "failed"]
JobSearchStepMode: TypeAlias = Literal["deterministic", "llm", "provider", "fallback", "mock"]
JobSearchResultSource: TypeAlias = Literal["local_mock", "live_search"]
JobSearchAnalysisMode: TypeAlias = Literal["deterministic", "llm", "fallback", "mock"]
JobSearchConfidenceLabel: TypeAlias = Literal["strong", "medium", "limited", "weak"]


class JobSearchResult(BaseModel):
    job_result_id: str
    title: str
    company: str
    location: str
    source: JobSearchResultSource = "local_mock"
    source_provider: str | None = None
    source_url: str | None = None
    raw_snippet: str | None = None
    description: str
    matched_keywords: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    match_score: int
    recommended_action: str
    analysis_mode: JobSearchAnalysisMode = "mock"
    confidence_label: JobSearchConfidenceLabel = "limited"


class JobSearchTraceStep(BaseModel):
    step_id: str
    job_search_run_id: str
    step_index: int
    name: str
    status: JobSearchStepStatus
    mode: JobSearchStepMode
    summary: str
    fallback_reason: str | None = None
    guardrails: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: float | None = None


class JobSearchRun(BaseModel):
    job_search_run_id: str
    session_id: str
    confirmed_profile_id: str
    query: str
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    search_mode: JobSearchMode = "local_mock"
    llm_enabled: bool = False
    search_provider: str | None = None
    status: JobSearchRunStatus = "completed"
    error_message: str | None = None
    results: list[JobSearchResult] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class JobSearchRunCreateRequest(BaseModel):
    session_id: str
    query: str | None = None
    search_mode: JobSearchMode = "live_search"
    use_llm: bool = False
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    max_results: int = 10


class JobSearchRunResponse(BaseModel):
    job_search_run: JobSearchRun
    profile_session: ProfileSession
    steps: list[JobSearchTraceStep] = Field(default_factory=list)


class JobSearchRunListResponse(BaseModel):
    items: list[JobSearchRun] = Field(default_factory=list)


class JobSearchTraceStepListResponse(BaseModel):
    items: list[JobSearchTraceStep] = Field(default_factory=list)
