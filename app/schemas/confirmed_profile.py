"""定义确认画像在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from typing_extensions import Literal

from app.schemas.profile_session import ProfileSession
from app.schemas.profile_review import ConfirmedResumeProfileResult
from app.schemas.resume import ResumeProfile


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


class ProfileSuggestionDecisionInput(BaseModel):
    """描述画像suggestiondecision的输入结构。"""
    section: str
    item_index: int | None = None
    field: str
    suggested_value: str | list[str]
    source_quote: str | None = None
    decision_status: Literal["accepted", "rejected", "edited"]


class MissingInfoAnswerInput(BaseModel):
    """描述missinginfo回答的输入结构。"""
    question: str
    answer: str


class ConfirmedProfileCreateRequest(BaseModel):
    """描述已确认画像create的输入结构。"""
    resume_record_id: int | None = None
    raw_resume_text: str
    baseline_profile: ResumeProfile
    confirmed_result: ConfirmedResumeProfileResult
    suggestion_decisions: list[ProfileSuggestionDecisionInput] = Field(default_factory=list)
    missing_info_answers: list[MissingInfoAnswerInput] = Field(default_factory=list)
    notes: str | None = None


class ConfirmedProfileRecordSummary(BaseModel):
    id: int
    confidence_label: str
    target_roles: list[str] = Field(default_factory=list)
    skill_count: int = 0
    project_count: int = 0
    work_experience_count: int = 0
    decision_count: int = 0
    missing_answer_count: int = 0
    created_at: str
    updated_at: str


class ConfirmedProfileRecordDetail(BaseModel):
    id: int
    raw_resume_text: str
    baseline_profile: ResumeProfile
    confirmed_result: ConfirmedResumeProfileResult
    suggestion_decisions: list[ProfileSuggestionDecisionInput] = Field(default_factory=list)
    missing_info_answers: list[MissingInfoAnswerInput] = Field(default_factory=list)
    notes: str | None = None
    created_at: str
    updated_at: str


class ConfirmedProfileCreateResponse(BaseModel):
    id: int
    summary: ConfirmedProfileRecordSummary
