"""定义搜索意图与约束在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ExplorationLevel = Literal["focused", "balanced", "exploratory"]
SearchMissionStatus = Literal["draft", "review", "confirmed"]
SearchMissionAnalysisMode = Literal["deterministic", "llm", "fallback"]


class SearchMissionClarificationAnswer(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=2000)

    @field_validator("question", "answer")
    @classmethod
    def _clean_text(cls, value: str) -> str:
        return " ".join(value.strip().split())


class SearchMissionInput(BaseModel):
    """描述搜索意图的输入结构。"""
    target_roles: list[str] = Field(default_factory=list)
    excluded_roles: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    ranking_priorities: list[str] = Field(default_factory=list)
    exploration_level: ExplorationLevel = "balanced"
    free_text: str | None = Field(default=None, max_length=2000)
    clarification_answers: list[SearchMissionClarificationAnswer] = Field(
        default_factory=list,
        max_length=3,
    )

    @field_validator(
        "target_roles",
        "excluded_roles",
        "preferred_industries",
        "locations",
        "work_arrangements",
        "employment_types",
        "must_have",
        "nice_to_have",
        "ranking_priorities",
    )
    @classmethod
    def _clean_list(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = " ".join(str(item).strip().split())
            key = text.casefold()
            if text and key not in seen:
                cleaned.append(text)
                seen.add(key)
        return cleaned

    @field_validator("free_text")
    @classmethod
    def _clean_free_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class SearchMissionInterpretation(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    adjacent_roles: list[str] = Field(default_factory=list)
    excluded_roles: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    ranking_priorities: list[str] = Field(default_factory=list)
    exploration_level: ExplorationLevel = "balanced"
    conflicts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list, max_length=3)


class SearchMission(BaseModel):
    search_mission_id: str
    user_id: str
    session_id: str
    confirmed_profile_id: str
    status: SearchMissionStatus
    input: SearchMissionInput
    mission: SearchMissionInterpretation
    analysis_mode: SearchMissionAnalysisMode = "deterministic"
    analysis_provider: str | None = None
    fallback_reason: str | None = None
    revision: int = 1
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None


class SearchMissionInterpretRequest(BaseModel):
    """描述搜索意图interpret的输入结构。"""
    use_llm: bool = False
    llm_provider: Literal["mock", "ollama", "deepseek"] = "deepseek"
