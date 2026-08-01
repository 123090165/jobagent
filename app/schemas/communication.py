from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CommunicationDraftStatus = Literal["generated", "approved", "sent", "failed", "dismissed"]


class CommunicationDraft(BaseModel):
    draft_id: str
    user_id: str
    saved_job_id: str
    application_id: str | None = None
    browser_capture_id: str | None = None
    draft_type: Literal["initial_greeting"] = "initial_greeting"
    generated_content: str
    approved_content: str | None = None
    status: CommunicationDraftStatus
    evidence_used: list[str] = Field(default_factory=list)
    avoid_claims: list[str] = Field(default_factory=list)
    generation_context: dict[str, object] = Field(default_factory=dict)
    analysis_provider: str | None = None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None = None


class CommunicationDraftGenerateRequest(BaseModel):
    resume_profile_id: str | None = None
    llm_provider: str | None = None


class CommunicationDraftUpdateRequest(BaseModel):
    approved_content: str | None = None
    status: Literal["approved", "dismissed"] | None = None

    @field_validator("approved_content")
    @classmethod
    def validate_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("approved_content cannot be empty")
        if len(cleaned) > 1200:
            raise ValueError("approved_content must be at most 1200 characters")
        return cleaned


class CommunicationSentConfirmation(BaseModel):
    platform_result: Literal["success"]
    sent_content: str
    sent_at: datetime

    @field_validator("sent_content")
    @classmethod
    def validate_sent_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("sent_content cannot be empty")
        if len(cleaned) > 1200:
            raise ValueError("sent_content must be at most 1200 characters")
        return cleaned


class CommunicationSentResult(BaseModel):
    draft: CommunicationDraft
    saved_job_id: str
    application_id: str
