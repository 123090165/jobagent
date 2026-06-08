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
