from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.search_ready_profile import SearchReadyProfile


class ProfileDraft(BaseModel):
    draft_id: str
    status: Literal["draft", "confirmed"] = "draft"
    search_ready_profile: SearchReadyProfile
    user_answers: dict[str, str] = Field(default_factory=dict)
    user_edit_snapshot: dict[str, Any] = Field(default_factory=dict)
    source_profile_snapshot: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
