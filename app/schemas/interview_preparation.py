from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

EvidenceStatus = Literal["supported", "partial", "unknown", "missing"]
SkillType = Literal["knowledge", "experience"]
ExperienceLevel = Literal[
    "work_experience",
    "project_experience",
    "practice_only",
    "conceptual_only",
    "no_experience",
    "uncertain",
]
EvidenceOrigin = Literal["resume", "user_reported", "none"]
DetailQuality = Literal["not_provided", "specific", "vague"]


class PreparationSkillGap(BaseModel):
    skill: str
    importance: Literal["high", "medium", "low"] = "medium"
    evidence_status: EvidenceStatus = "unknown"
    skill_type: SkillType = "knowledge"
    jd_evidence: str
    profile_evidence: list[str] = Field(default_factory=list)
    rationale: str
    evidence_origin: EvidenceOrigin = "none"


class PreparationAnswerOption(BaseModel):
    value: ExperienceLevel
    label: str
    description: str


class PreparationQuestion(BaseModel):
    question_id: str
    skill: str
    prompt: str
    why_asked: str
    options: list[PreparationAnswerOption] = Field(default_factory=list)


class LearningResource(BaseModel):
    topic: str
    title: str
    url: str
    source: str
    level: str = "review"
    reason: str


class PreparationAnswer(BaseModel):
    question_id: str
    experience_level: ExperienceLevel | None = None
    detail: str | None = Field(default=None, max_length=5000)
    detail_quality: DetailQuality = "not_provided"
    # Kept while reading older workspaces and external-chat payloads.
    answer: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def require_structured_or_legacy_answer(self) -> "PreparationAnswer":
        if self.experience_level is None and not (self.answer or "").strip():
            raise ValueError("An experience level or legacy answer is required")
        if self.detail is not None:
            self.detail = self.detail.strip() or None
        if self.answer is not None:
            self.answer = self.answer.strip() or None
        return self


class PreparationRecommendation(BaseModel):
    title: str
    action: str
    action_type: Literal[
        "learning", "experience_inventory", "interview_story", "capability_gap"
    ] = "experience_inventory"
    skill: str | None = None
    evidence_basis: list[str] = Field(default_factory=list)


class InterviewPreparationWorkspace(BaseModel):
    preparation_id: str
    saved_job_id: str
    user_id: str
    resume_profile_id: str | None = None
    source_analysis_id: str | None = None
    status: Literal["questions_ready", "paused", "completed", "stopped"] = "questions_ready"
    skill_gaps: list[PreparationSkillGap] = Field(default_factory=list)
    questions: list[PreparationQuestion] = Field(default_factory=list)
    answers: list[PreparationAnswer] = Field(default_factory=list)
    learning_resources: list[LearningResource] = Field(default_factory=list)
    recommendations: list[PreparationRecommendation] = Field(default_factory=list)
    analysis_mode: str
    analysis_provider: str | None = None
    fallback_reason: str | None = None
    resource_mode: str = "none"
    resource_warning: str | None = None
    created_at: datetime
    updated_at: datetime


class PreparationGenerateRequest(BaseModel):
    resume_profile_id: str | None = None
    llm_provider: str | None = None


class PreparationAnswerRequest(BaseModel):
    answers: list[PreparationAnswer] = Field(default_factory=list, max_length=5)
    llm_provider: str | None = None
    action: Literal["save", "complete", "stop"] = "complete"
