from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.interview_preparation import ExperienceLevel


class SkillCalibration(BaseModel):
    skill: str
    resume_signal: str
    actual_level: ExperienceLevel
    confidence: Literal["low", "medium", "high"]
    private_notes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    scenario_fact_refs: list[str] = Field(default_factory=list)


class SyntheticScenarioFact(BaseModel):
    fact_id: str
    statement: str
    kind: Literal["ability_calibration", "hidden_history", "behavioral_constraint"]
    basis: Literal["resume_inference", "evaluation_variation"]
    evidence_refs: list[str] = Field(default_factory=list)
    allowed_in_candidate_answer: bool = False


class CandidatePersona(BaseModel):
    archetype: str
    internal_summary: str
    confidence_style: Literal["underconfident", "calibrated", "overconfident"]
    communication_style: Literal["terse", "balanced", "detailed"]
    disclosure_style: Literal["guarded", "honest", "self_promoting"]
    concerns: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    skill_calibrations: list[SkillCalibration] = Field(default_factory=list)
    synthetic_scenario_memory: list[SyntheticScenarioFact] = Field(default_factory=list)


class CandidateTurn(BaseModel):
    question_id: str
    skill: str
    response_mode: Literal["option", "free_text"]
    selected_option_id: str | None = None
    free_text: str | None = None
    experience_level: ExperienceLevel | None = None
    detail: str | None = None
    private_reason: str
    candidate_reaction: str
    fact_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def upgrade_legacy_turn(cls, data: object) -> object:
        if isinstance(data, dict) and "response_mode" not in data:
            return {**data, "response_mode": "option"}
        return data


class CandidateSelfAssessment(BaseModel):
    felt_understood: int = Field(ge=0, le=5)
    truthfulness: int = Field(ge=0, le=5)
    learning_value: int = Field(ge=0, le=5)
    interview_value: int = Field(ge=0, le=5)
    actionability: int = Field(ge=0, le=5)
    helpful_items: list[str] = Field(default_factory=list)
    unhelpful_items: list[str] = Field(default_factory=list)
    misunderstandings: list[str] = Field(default_factory=list)
    missing_support: list[str] = Field(default_factory=list)
    candidate_reflection: str


class RuleCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class PreparationEvaluationReport(BaseModel):
    evaluation_id: str
    generated_at: datetime
    profile_id: str
    saved_job_id: str
    user_id: str
    saved_job_origin_id: str | None = None
    association_method: str
    evaluation_model: str
    preparation_provider: str
    profile_memory: dict[str, object]
    persona_memory: CandidatePersona
    episodic_memory: list[CandidateTurn]
    preparation_result: dict[str, object]
    self_assessment: CandidateSelfAssessment
    rule_checks: list[RuleCheck]
    passed: bool
