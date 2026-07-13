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
GenerationMode = Literal["deterministic", "llm", "fallback"]
AnswerMode = Literal["option", "free_text"]
EvidenceTransition = Literal["supported", "partial", "unknown", "missing"]
RouteAction = Literal[
    "ask_evidence", "learning", "capability_gap", "clarify", "next_skill"
]
DetailPolicy = Literal["required", "optional", "not_needed"]
ResolutionSource = Literal["option", "llm_classified", "fallback_uncertain", "legacy"]


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
    option_id: str
    value: ExperienceLevel
    label: str
    description: str
    evidence_transition: EvidenceTransition
    route: RouteAction
    detail_policy: DetailPolicy = "optional"
    follow_up_prompt: str | None = None

    @model_validator(mode="before")
    @classmethod
    def upgrade_legacy_option(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        value = data.get("value")
        defaults = {
            "work_experience": ("supported", "ask_evidence", "required"),
            "project_experience": ("supported", "ask_evidence", "required"),
            "practice_only": ("partial", "learning", "optional"),
            "conceptual_only": ("partial", "learning", "not_needed"),
            "no_experience": ("missing", "capability_gap", "not_needed"),
            "uncertain": ("unknown", "clarify", "optional"),
        }
        if value not in defaults:
            return data
        evidence, route, detail_policy = defaults[value]
        upgraded = {**data}
        upgraded.setdefault("option_id", str(value))
        upgraded.setdefault("evidence_transition", evidence)
        upgraded.setdefault("route", route)
        upgraded.setdefault("detail_policy", detail_policy)
        if upgraded["detail_policy"] == "required":
            upgraded.setdefault(
                "follow_up_prompt",
                "Briefly describe your personal contribution and how the result was evaluated.",
            )
        return upgraded

    @model_validator(mode="after")
    def validate_transition(self) -> "PreparationAnswerOption":
        allowed = {
            "work_experience": ({"supported", "partial"}, {"ask_evidence", "next_skill"}),
            "project_experience": ({"supported", "partial"}, {"ask_evidence", "next_skill"}),
            "practice_only": ({"partial"}, {"ask_evidence", "learning", "next_skill"}),
            "conceptual_only": ({"partial"}, {"learning", "next_skill"}),
            "no_experience": ({"missing"}, {"learning", "capability_gap", "next_skill"}),
            "uncertain": ({"unknown"}, {"clarify", "next_skill"}),
        }
        evidence, routes = allowed[self.value]
        if self.evidence_transition not in evidence or self.route not in routes:
            raise ValueError(
                f"Invalid transition for {self.value}: "
                f"{self.evidence_transition}/{self.route}"
            )
        if self.detail_policy == "required" and not (self.follow_up_prompt or "").strip():
            raise ValueError("A required detail option needs a follow-up prompt")
        return self


class PreparationQuestion(BaseModel):
    question_id: str
    skill: str
    prompt: str
    why_asked: str
    options: list[PreparationAnswerOption] = Field(default_factory=list)
    free_text_allowed: bool = True
    free_text_prompt: str = (
        "If none of these options describes your situation accurately, explain what is different."
    )

    @model_validator(mode="after")
    def require_distinct_options(self) -> "PreparationQuestion":
        ids = [item.option_id for item in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("Question option IDs must be unique")
        return self


class LearningResource(BaseModel):
    topic: str
    title: str
    url: str
    source: str
    level: str = "review"
    reason: str


class PreparationAnswer(BaseModel):
    question_id: str
    response_mode: AnswerMode = "option"
    selected_option_id: str | None = None
    free_text: str | None = Field(default=None, max_length=5000)
    experience_level: ExperienceLevel | None = None
    detail: str | None = Field(default=None, max_length=5000)
    detail_quality: DetailQuality = "not_provided"
    # Kept while reading older workspaces and external-chat payloads.
    answer: str | None = Field(default=None, max_length=5000)
    evidence_transition: EvidenceTransition | None = None
    route: RouteAction | None = None
    resolution_source: ResolutionSource | None = None

    @model_validator(mode="after")
    def require_structured_or_legacy_answer(self) -> "PreparationAnswer":
        if self.response_mode == "option":
            if self.experience_level is None and not self.selected_option_id:
                if (self.answer or "").strip():
                    self.response_mode = "free_text"
                    self.free_text = self.answer
                else:
                    raise ValueError("An option selection is required")
        elif not (self.free_text or self.answer or "").strip():
            raise ValueError("A free-text response is required")
        if self.detail is not None:
            self.detail = self.detail.strip() or None
        if self.free_text is not None:
            self.free_text = self.free_text.strip() or None
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


class PreparationGenerationStage(BaseModel):
    mode: GenerationMode
    provider: str | None = None
    prompt_version: str
    attempts: int = Field(default=0, ge=0, le=2)
    fallback_reason: str | None = None
    attempt_errors: list[str] = Field(default_factory=list)


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
    question_generation: PreparationGenerationStage | None = None
    recommendation_generation: PreparationGenerationStage | None = None
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
