from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from app.schemas.profile_session import ProfileSession


class ConfirmedProfile(BaseModel):
    confirmed_profile_id: str
    session_id: str
    resume_document_id: str
    parsed_review_id: str
    profile_draft_id: str
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
    missing_info_questions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ConfirmedProfileResponse(BaseModel):
    confirmed_profile: ConfirmedProfile
    profile_session: ProfileSession
