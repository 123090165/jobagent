from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.resume import ResumeProfile


class ResumeProfileReviewRequest(BaseModel):
    resume_text: str
    target_roles: list[str] = Field(default_factory=list)


class ResumeProfileReviewResult(BaseModel):
    parsed_profile: ResumeProfile
    quality_warnings: list[str] = Field(default_factory=list)
    missing_info_questions: list[str] = Field(default_factory=list)
    suggested_edits: list[str] = Field(default_factory=list)
    editable_sections: list[str] = Field(default_factory=list)
    confidence_label: str = "medium"


class ResumeProfileUserEdits(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    additional_skills: list[str] = Field(default_factory=list)
    project_clarifications: list[str] = Field(default_factory=list)
    work_experience_clarifications: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    notes: str | None = None


class ResumeProfileConfirmRequest(BaseModel):
    parsed_profile: ResumeProfile
    user_edits: ResumeProfileUserEdits = Field(default_factory=ResumeProfileUserEdits)


class ResumeProfileConfirmationSummary(BaseModel):
    confirmed_sections: list[str] = Field(default_factory=list)
    added_target_roles: list[str] = Field(default_factory=list)
    added_skills: list[str] = Field(default_factory=list)
    added_project_clarifications_count: int = 0
    added_work_experience_clarifications_count: int = 0
    constraints_count: int = 0


class ConfirmedResumeProfileResult(BaseModel):
    confirmed_profile: ResumeProfile
    user_confirmed_data: ResumeProfileUserEdits
    confirmation_summary: ResumeProfileConfirmationSummary
    remaining_warnings: list[str] = Field(default_factory=list)
    confidence_label: str = "medium"


class ProfileSearchContext(BaseModel):
    confirmed_profile: ResumeProfile
    user_confirmed_data: ResumeProfileUserEdits = Field(
        default_factory=ResumeProfileUserEdits
    )
