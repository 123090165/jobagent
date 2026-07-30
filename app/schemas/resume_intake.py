"""定义resume intake在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.profile_session import ProfileSession
from app.schemas.resume_document import ResumeDocument


class ResumeTextRequest(BaseModel):
    """描述text的输入结构。"""
    text: str


class ResumeIntakeResponse(BaseModel):
    resume_document: ResumeDocument
    profile_session: ProfileSession
