from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EvidenceStatus = Literal["supported", "partial", "unknown", "missing"]
SkillType = Literal["knowledge", "experience"]


class PreparationSkillGap(BaseModel):
    skill: str
    importance: Literal["high", "medium", "low"] = "medium"
    evidence_status: EvidenceStatus = "unknown"
    skill_type: SkillType = "knowledge"
    jd_evidence: str
    profile_evidence: list[str] = Field(default_factory=list)
    rationale: str


class PreparationQuestion(BaseModel):
    question_id: str
    skill: str
    prompt: str
    why_asked: str


class LearningResource(BaseModel):
    topic: str
    title: str
    url: str
    source: str
    level: str = "review"
    reason: str


class PreparationAnswer(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=5000)


class PreparationRecommendation(BaseModel):
    title: str
    action: str
    evidence_basis: list[str] = Field(default_factory=list)


class InterviewPreparationWorkspace(BaseModel):
    preparation_id: str
    saved_job_id: str
    user_id: str
    resume_profile_id: str | None = None
    source_analysis_id: str | None = None
    status: Literal["questions_ready", "completed"] = "questions_ready"
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
