"""定义搜索结果反馈在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

JobSearchFeedbackType = Literal[
    "relevant",
    "irrelevant",
    "duplicate",
    "stale",
    "insufficient_jd",
]


class JobSearchResultFeedbackUpsertRequest(BaseModel):
    """描述职位搜索结果反馈upsert的输入结构。"""
    feedback_type: JobSearchFeedbackType
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def _clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class JobSearchResultFeedback(BaseModel):
    feedback_id: str
    user_id: str
    job_search_run_id: str
    job_result_id: str
    confirmed_profile_id: str
    resume_profile_id: str | None = None
    source_provider: str | None = None
    feedback_type: JobSearchFeedbackType
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class JobSearchResultFeedbackListResponse(BaseModel):
    items: list[JobSearchResultFeedback] = Field(default_factory=list)
