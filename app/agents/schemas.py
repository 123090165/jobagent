from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GeneratedGroundedQuestionDraft(BaseModel):
    question: str
    why_asked: str
    expected_answer_points: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"]
    question_type: Literal["basic", "technical", "architecture", "tradeoff"]
