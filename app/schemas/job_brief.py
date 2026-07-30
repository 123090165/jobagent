"""定义Job Brief在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class JobBriefContent(BaseModel):
    decision_summary: str
    fit_signals: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    resume_actions: list[str] = Field(default_factory=list)
    interview_focus: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class JobBrief(BaseModel):
    job_brief_id: str
    saved_job_id: str
    user_id: str
    resume_profile_id: str | None = None
    source_analysis_id: str | None = None
    version: int
    content: JobBriefContent
    analysis_mode: str
    analysis_provider: str | None = None
    fallback_reason: str | None = None
    created_at: datetime


class JobBriefGenerateRequest(BaseModel):
    """描述职位决策简报generate的输入结构。"""
    resume_profile_id: str | None = None
    llm_provider: str | None = None


class JobBriefListResponse(BaseModel):
    items: list[JobBrief] = Field(default_factory=list)
