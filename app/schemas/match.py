from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MatchLevel = Literal["matched", "partial", "missing"]


class RequirementMatch(BaseModel):
    requirement: str
    category: str = "general"
    importance: str = "must"
    match_level: MatchLevel
    resume_evidence: list[str] = Field(default_factory=list)
    gap_reason: str | None = None
    improvement_hint: str | None = None


class MatchReport(BaseModel):
    overall_score: float
    skill_score: float
    project_score: float
    experience_score: float
    keyword_coverage: float
    matched_points: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    apply_recommendation: str
    short_term_suggestions: list[str] = Field(default_factory=list)
    long_term_suggestions: list[str] = Field(default_factory=list)
    requirement_matches: list[RequirementMatch] = Field(default_factory=list)


class RewriteSuggestion(BaseModel):
    original: str
    suggestion: str
    reason: str


class ResumeOptimizationResult(BaseModel):
    overall_issues: list[str] = Field(default_factory=list)
    keywords_to_add: list[str] = Field(default_factory=list)
    skills_section_suggestions: list[str] = Field(default_factory=list)
    project_rewrite_suggestions: list[RewriteSuggestion] = Field(default_factory=list)
    jd_targeted_bullets: list[str] = Field(default_factory=list)
    do_not_exaggerate: list[str] = Field(default_factory=list)
    missing_info_needed: list[str] = Field(default_factory=list)


class ChallengeQuestion(BaseModel):
    question: str
    evaluates: str
    answer_framework: str


class ProjectChallengeReport(BaseModel):
    basic_questions: list[ChallengeQuestion] = Field(default_factory=list)
    technical_deep_dive_questions: list[ChallengeQuestion] = Field(default_factory=list)
    architecture_questions: list[ChallengeQuestion] = Field(default_factory=list)
    tradeoff_questions: list[ChallengeQuestion] = Field(default_factory=list)
    interviewer_concerns: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
