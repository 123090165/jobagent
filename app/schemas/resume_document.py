"""定义原始简历文档在 API、领域服务和 JSON 快照之间共用的 Pydantic 契约。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ResumeDocumentSourceType = Literal["text", "file"]


class ResumeDocument(BaseModel):
    resume_document_id: str
    session_id: str
    source_type: ResumeDocumentSourceType
    filename: str | None
    file_type: str | None
    text: str
    text_length: int
    created_at: datetime
    updated_at: datetime
