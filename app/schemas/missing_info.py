from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


QuestionPriority = Literal["high", "medium", "low"]


class MissingInfoQuestion(BaseModel):
    question: str
    reason: str
    related_skill: str | None = None
    priority: QuestionPriority


class MissingInfoReport(BaseModel):
    questions: list[MissingInfoQuestion] = Field(default_factory=list)
    summary: str
