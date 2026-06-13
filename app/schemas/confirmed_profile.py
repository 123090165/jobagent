from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.profile_review import ConfirmedResumeProfileResult
from app.schemas.resume import ResumeProfile

VALID_DECISION_STATUSES = {"accepted", "edited", "rejected"}


class ProfileSuggestionDecisionInput(BaseModel):
    section: str
    item_index: int | None = None
    field: str
    suggested_value: str | list[str]
    edited_value: str | list[str] | None = None
    source_quote: str | None = None
    decision_status: str
    confidence_label: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @field_validator("decision_status")
    @classmethod
    def validate_decision_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_DECISION_STATUSES:
            raise ValueError("decision_status must be accepted, edited, or rejected")
        return normalized


class MissingInfoAnswerInput(BaseModel):
    question: str
    answer: str


class ConfirmedProfileCreateRequest(BaseModel):
    raw_resume_text: str
    baseline_profile: ResumeProfile
    confirmed_result: ConfirmedResumeProfileResult
    suggestion_decisions: list[ProfileSuggestionDecisionInput] = Field(default_factory=list)
    missing_info_answers: list[MissingInfoAnswerInput] = Field(default_factory=list)
    resume_record_id: int | None = None
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
