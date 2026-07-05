from __future__ import annotations

from datetime import datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field

from app.schemas.profile_session import ProfileSession

JobSearchMode: TypeAlias = Literal["local_mock", "live_search", "browser_helper"]
JobSearchRunStatus: TypeAlias = Literal["pending", "running", "completed", "failed"]
JobSearchStepStatus: TypeAlias = Literal["pending", "running", "completed", "failed"]
JobSearchStepMode: TypeAlias = Literal["deterministic", "llm", "provider", "fallback", "mock"]
JobSearchResultSource: TypeAlias = Literal["local_mock", "live_search"]
JobSearchAnalysisMode: TypeAlias = Literal["deterministic", "llm", "fallback", "mock"]
JobSearchConfidenceLabel: TypeAlias = Literal["strong", "medium", "limited", "weak"]
JobSearchPlanningMode: TypeAlias = Literal["deterministic", "llm", "fallback"]
JobSearchSourceKind: TypeAlias = Literal[
    "mock",
    "native_job_board",
    "native_api",
    "search_engine",
    "direct_crawler",
    "browser_helper",
    "hybrid",
]
JobSearchSelectedSource: TypeAlias = Literal["cuhksz_career", "linkedin", "remoteok"]


class JobSearchIntent(BaseModel):
    role_titles: list[str] = Field(default_factory=list)
    role_families: list[str] = Field(default_factory=list)
    industry_domains: list[str] = Field(default_factory=list)
    evidence_skills: list[str] = Field(default_factory=list)
    generic_tools: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    broad_queries: list[str] = Field(default_factory=list)
    domain_queries: list[str] = Field(default_factory=list)
    evidence_queries: list[str] = Field(default_factory=list)
    tool_queries: list[str] = Field(default_factory=list)
    mode: JobSearchPlanningMode = "deterministic"
    fallback_reason: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)


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
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    evidence_quotes: list[str] = Field(default_factory=list)
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
    details: dict[str, object] = Field(default_factory=dict)
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
    selected_sources: list[str] = Field(default_factory=list)
    status: JobSearchRunStatus = "completed"
    error_message: str | None = None
    results: list[JobSearchResult] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class JobSearchRunCreateRequest(BaseModel):
    session_id: str
    query: str | None = None
    search_mode: JobSearchMode = "live_search"
    search_provider: str | None = None
    selected_sources: list[JobSearchSelectedSource] = Field(default_factory=list)
    use_llm: bool = False
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    max_results: int = 10


class BrowserHelperJobCandidate(BaseModel):
    title: str
    company: str | None = None
    location: str | None = None
    source_url: str | None = None
    source_provider: str = "browser_helper"
    snippet: str
    raw_description: str | None = None
    discovery_query: str | None = None
    discovery_rank: int | None = None
    detail_status: str | None = "browser_helper_payload"
    provider_warnings: list[str] = Field(default_factory=list)


class BrowserHelperJobSearchRunCreateRequest(BaseModel):
    session_id: str
    query: str | None = None
    helper_version: str | None = None
    platforms: list[str] = Field(default_factory=list)
    selected_sources: list[JobSearchSelectedSource] = Field(default_factory=list)
    use_llm: bool = False
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    max_results: int = 10
    candidates: list[BrowserHelperJobCandidate] = Field(default_factory=list)


class JobSearchRunResponse(BaseModel):
    job_search_run: JobSearchRun
    profile_session: ProfileSession
    steps: list[JobSearchTraceStep] = Field(default_factory=list)


class JobSearchPreviewResponse(BaseModel):
    session_id: str
    confirmed_profile_id: str
    search_mode: JobSearchMode
    search_provider: str | None = None
    selected_sources: list[str] = Field(default_factory=list)
    llm_enabled: bool = False
    llm_provider: str | None = None
    query: str
    locations: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    provider_queries: list[str] = Field(default_factory=list)
    search_intent: JobSearchIntent | None = None
    search_source_kind: JobSearchSourceKind = "native_job_board"
    search_source_notes: list[str] = Field(default_factory=list)
    recall_queries: list[str] = Field(default_factory=list)
    ranking_signals: list[str] = Field(default_factory=list)
    provider_search_terms: list[str] = Field(default_factory=list)
    provider_search_urls: list[str] = Field(default_factory=list)
    provider_query_count: int = 0
    estimated_provider_requests: int = 0
    estimated_candidate_pool_size: int = 0
    estimated_llm_planning_requests: int = 0
    estimated_llm_filtering_requests: int = 0
    estimated_llm_analysis_requests: int = 0
    estimated_total_llm_requests: int = 0
    query_strategy_notes: list[str] = Field(default_factory=list)
    search_signal_terms: list[str] = Field(default_factory=list)
    excluded_signals: list[str] = Field(default_factory=list)
    ranking_policy: str
    planning_mode: JobSearchPlanningMode
    fallback_reason: str | None = None
    quality_warnings: list[str] = Field(default_factory=list)


class JobSearchRunListResponse(BaseModel):
    items: list[JobSearchRun] = Field(default_factory=list)


class JobSearchTraceStepListResponse(BaseModel):
    items: list[JobSearchTraceStep] = Field(default_factory=list)
