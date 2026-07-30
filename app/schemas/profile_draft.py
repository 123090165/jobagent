"""定义画像草稿在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.profile_session import ProfileSession
from app.schemas.search_ready_profile import SearchReadyProfile


class ProfileDraft(BaseModel):
    profile_draft_id: str = ""
    session_id: str = ""
    parsed_review_id: str = ""
    summary: str = ""
    target_roles: list[str] = Field(default_factory=list)
    target_directions: list[str] = Field(default_factory=list)
    core_skills: list[str] = Field(default_factory=list)
    supporting_skills: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_info_questions: list[str] = Field(default_factory=list)
    draft_id: str | None = None
    status: str | None = None
    search_ready_profile: SearchReadyProfile | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_configured: bool | None = None
    llm_provider_reason: str | None = None
    user_answers: dict[str, str] = Field(default_factory=dict)
    user_edit_snapshot: dict[str, object] = Field(default_factory=dict)
    source_profile_snapshot: dict[str, object] | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _hydrate_compat_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if not data.get("profile_draft_id") and data.get("draft_id"):
            data["profile_draft_id"] = data["draft_id"]
        if not data.get("draft_id") and data.get("profile_draft_id"):
            data["draft_id"] = data["profile_draft_id"]
        return data


class ProfileDraftResponse(BaseModel):
    profile_draft: ProfileDraft
    profile_session: ProfileSession


class UpdateProfileDraftRequest(BaseModel):
    """描述画像草稿的输入结构。"""
    summary: str | None = None
    target_roles: list[str] | None = None
    target_directions: list[str] | None = None
    core_skills: list[str] | None = None
    supporting_skills: list[str] | None = None
    search_keywords: list[str] | None = None
    preferred_locations: list[str] | None = None
    work_arrangements: list[str] | None = None
    strengths: list[str] | None = None
    risks: list[str] | None = None
    missing_info_questions: list[str] | None = None
