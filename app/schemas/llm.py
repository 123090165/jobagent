from __future__ import annotations

from pydantic import BaseModel


class LLMStatusResponse(BaseModel):
    provider: str
    configured: bool
    model: str | None = None
    base_url: str | None = None
    reason: str | None = None
