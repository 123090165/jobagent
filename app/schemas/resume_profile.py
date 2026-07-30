"""定义可复用简历画像在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ResumeProfile(BaseModel):
    resume_profile_id: str
    user_id: str
    source_session_id: str | None = None
    source_confirmed_profile_id: str | None = None
    name: str
    summary: str
    target_roles: list[str] = Field(default_factory=list)
    target_directions: list[str] = Field(default_factory=list)
    core_skills: list[str] = Field(default_factory=list)
    supporting_skills: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    profile: dict[str, object] = Field(default_factory=dict)
    raw_resume_text: str | None = None
    is_default: bool = False
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ResumeProfileListResponse(BaseModel):
    items: list[ResumeProfile] = Field(default_factory=list)


class ResumeProfileUpdateRequest(BaseModel):
    """描述画像update的输入结构。"""
    name: str | None = None
    summary: str | None = None
    target_roles: list[str] | None = None
    target_directions: list[str] | None = None
    core_skills: list[str] | None = None
    supporting_skills: list[str] | None = None
    search_keywords: list[str] | None = None
    preferred_locations: list[str] | None = None
    work_arrangements: list[str] | None = None
    strengths: list[str] | None = None
    risks: list[str] | None = None
    raw_resume_text: str | None = None
