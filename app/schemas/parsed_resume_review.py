"""定义简历解析审阅在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.profile_session import ProfileSession


class ParsedResumeReview(BaseModel):
    parsed_review_id: str
    session_id: str
    resume_document_id: str
    basic_info: dict[str, Any] = Field(default_factory=dict)
    education: list[dict[str, Any]] = Field(default_factory=list)
    work_experience: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    skills: dict[str, Any] = Field(default_factory=dict)
    target_signals: list[str] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)
    missing_info_questions: list[str] = Field(default_factory=list)
    raw_parser_output: dict[str, Any] | None = None
    analysis_mode: Literal["deterministic", "llm", "llm_guided", "fallback"] = "deterministic"
    analysis_provider: str | None = None
    analysis_warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ParsedResumeReviewResponse(BaseModel):
    parsed_review: ParsedResumeReview
    profile_session: ProfileSession
