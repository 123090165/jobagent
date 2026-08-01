from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.saved_job import SavedJob, SavedJobAnalysis
from app.schemas.communication import CommunicationDraft
from app.schemas.tailored_resume import TailoredResumeVersion

ApplicationStage = Literal[
    "not_started",
    "contacted",
    "recruiter_replied",
    "resume_requested",
    "resume_ready",
    "resume_sent",
    "interview",
    "closed",
]
ApplicationNextAction = Literal[
    "generate_greeting",
    "review_greeting",
    "wait_for_reply",
    "review_reply",
    "generate_resume",
    "review_resume",
    "send_resume",
    "prepare_interview",
    "none",
]
ExternalApplicationStage = Literal[
    "contacted",
    "resume_requested",
    "resume_sent",
    "interview",
    "closed",
]
ApplicationEventSource = Literal["web", "browser_helper", "system", "user"]
ApplicationEventType = Literal[
    "job_saved",
    "analysis_generated",
    "greeting_generated",
    "greeting_edited",
    "greeting_sent",
    "resume_requested",
    "tailored_resume_generated",
    "resume_confirmed",
    "resume_sent",
    "stage_changed",
]


class JobApplication(BaseModel):
    application_id: str
    user_id: str
    saved_job_id: str
    stage: ApplicationStage
    next_action: ApplicationNextAction
    last_activity_at: datetime
    contacted_at: datetime | None = None
    replied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class JobApplicationCreateRequest(BaseModel):
    next_action: ApplicationNextAction = "generate_greeting"


class JobApplicationUpdateRequest(BaseModel):
    stage: ApplicationStage | None = None
    next_action: ApplicationNextAction | None = None
    detail: str | None = None

    @model_validator(mode="after")
    def require_change(self) -> "JobApplicationUpdateRequest":
        if self.stage is None and self.next_action is None:
            raise ValueError("stage or next_action is required")
        return self


class ExternalApplicationProgressRequest(BaseModel):
    stage: ExternalApplicationStage
    detail: str | None = Field(default=None, max_length=500)


class ApplicationEvent(BaseModel):
    event_id: str
    application_id: str
    user_id: str
    event_type: ApplicationEventType
    source: ApplicationEventSource
    detail: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class SavedJobWorkspace(BaseModel):
    job: SavedJob
    application: JobApplication | None = None
    latest_analysis: SavedJobAnalysis | None = None
    communication_draft: CommunicationDraft | None = None
    tailored_resume: TailoredResumeVersion | None = None
    allowed_stage_transitions: list[ApplicationStage] = Field(default_factory=list)
    events: list[ApplicationEvent] = Field(default_factory=list)
