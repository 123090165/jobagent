from __future__ import annotations

from pydantic import BaseModel

from app.schemas.profile_session import ProfileSession
from app.schemas.resume_document import ResumeDocument


class ResumeTextRequest(BaseModel):
    text: str


class ResumeIntakeResponse(BaseModel):
    resume_document: ResumeDocument
    profile_session: ProfileSession
