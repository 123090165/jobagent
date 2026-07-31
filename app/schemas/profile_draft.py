from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.profile_session import ProfileSession


class ProfileDraft(BaseModel):
    profile_draft_id: str = ""
    session_id: str = ""
    parsed_review_id: str = ""
    summary: str = ""
    target_roles: list[str] = Field(default_factory=list)
    target_directions: list[str] = Field(default_factory=list)
    core_skills: list[str] = Field(default_factory=list)
    supporting_skills: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_info_questions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProfileDraftResponse(BaseModel):
    profile_draft: ProfileDraft
    profile_session: ProfileSession


class UpdateProfileDraftRequest(BaseModel):
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
    missing_info_questions: list[str] | None = None
